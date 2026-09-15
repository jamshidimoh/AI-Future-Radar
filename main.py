import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from src.dedup import filter_new_items, load_seen, load_source_history, mark_as_seen, save_seen
from src.editorial import enrich_items, filter_ai_relevance
from src.fetch_google_news import fetch_google_news_items
from src.fetch_rss import fetch_rss_items
from src.fetch_youtube import fetch_youtube_items
from src.interview_evidence import has_interview_evidence
from src.llm_router_light import QuotaExceeded
from src.logging_setup import configure_logging
from src.mission_selector import _source_tier
from src.publication_contract import unique_candidates
from src.send_telegram import format_post, resolve_source_image, send_to_telegram_safe
from src.signal_engine import enrich_signal_items
from src.state_io import StateCorruptionError
from src.story_gate import gate_story_candidates
from src.summarize import summarize_item
from src.unified_editorial_selection import select_regular_portfolio

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
LEADER_CONFIG_PATH = ROOT / "config" / "leader_watchlist.yaml"
SELECTION_POLICY_PATH = ROOT / "config" / "selection_policy.yaml"
TELEGRAM_SAFE_TEXT_LIMIT = 3900
PROTECTED_SUMMARY_SCORE_FLOOR = 60.0
NORMAL_SCORE_FLOOR = 60.0


def _publication_identity(item: dict) -> str:
    return str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or id(item))


def load_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f: return yaml.safe_load(f)

def _text(item): return " ".join(str(item.get(k) or "") for k in ("title", "summary", "description")).lower()
def _contains_person(text, name): return str(name or "").strip().lower() in str(text or "").lower()
def _has_explicit_interview_evidence(item): return has_interview_evidence(item)
def _direct_interview_signal(item): return has_interview_evidence(item)

def _leader_source_authority(item):
    """Normalize leader source authority so higher values mean stronger provenance."""
    try:
        existing = item.get("leader_source_authority")
    except AttributeError:
        return 0
    if existing is not None:
        try:
            return int(existing)
        except (TypeError, ValueError):
            pass
    try:
        tier = _source_tier(item)
    except Exception as exc:
        logger.warning("Could not determine source authority: %s", exc, exc_info=True)
        tier = None
    try:
        tier = int(tier) if tier is not None else None
    except (TypeError, ValueError):
        tier = None
    return max(0, 4 - tier) if tier is not None else 0

def _apply_signal_ranking(items):
    """Historical pre-selection signal uplift: 30% signal on top of pre-signal editorial score."""
    for item in items:
        try:
            base = float(item.get("editorial_score_pre_signal", item.get("editorial_score", 0)) or 0.0)
        except (TypeError, ValueError):
            base = 0.0
        try:
            signal = float(item.get("signal_score", 0) or 0.0)
        except (TypeError, ValueError):
            signal = 0.0
        item["editorial_score_pre_signal"] = round(base, 2)
        item["editorial_score"] = round(base + 0.30 * signal, 2)
    return items

def _leader_activity_signal(item):
    ctype = str(item.get("content_type") or "").lower().strip()
    if ctype == "interview": return False
    text = _text(item)
    activity_terms = ("launch", "launched", "release", "released", "unveil", "introduced", "product", "model", "platform", "startup", "company", "fund", "investment", "acquisition", "partnership", "appoint", "appointed", "research project", "initiative", "new course", "course", "paper", "project", "announcement", "funding", "raises", "raised", "joins", "founded", "founder", "ceo")
    return ctype in {"product_news", "official"} or bool(item.get("leader_activity_signal")) or any(term in text for term in activity_terms)

def _leader_people(leader_config):
    names, priorities = [], {}
    for group in (leader_config.get("people") or {}).values():
        for person in (group.get("names") or []):
            name = str(person).strip()
            if name: names.append(name); priorities[name] = int(group.get("priority", 0) or 0)
    return sorted(set(names)), priorities

def _merge_unique_dicts(*lists, key):
    out, seen = [], set()
    for seq in lists:
        for item in seq or []:
            value = str(item.get(key) or "")
            if value not in seen: seen.add(value); out.append(item)
    return out

def _mark_leader_items(items):
    for item in items: item["is_leader"] = True; item["is_leader_watch"] = True
    return items

def _annotate_named_leader_interviews(items, leader_people, leader_priorities=None):
    names = sorted({str(x).strip() for x in (leader_people or []) if str(x).strip()}, key=len, reverse=True)
    priorities = {str(k).strip(): int(v or 0) for k, v in (leader_priorities or {}).items()}
    matched = protected = watch_candidates = 0
    for item in items:
        existing = str(item.get("leader") or item.get("watch_person") or "").strip()
        if existing:
            if existing in names:
                watch_candidates += 1
                item["leader_priority"] = priorities.get(existing, int(item.get("leader_priority", 0) or 0))
                if _direct_interview_signal(item):
                    item["_named_leader_interview"] = True
                    item["is_leader_watch"] = True
                    item["leader_watch_protected"] = True
                    matched += 1
                elif _leader_activity_signal(item):
                    item["leader_activity_signal"] = True
                    item["is_leader_watch"] = True
                    item["leader_watch_protected"] = True
                    protected += 1
            continue
        text = _text(item)
        matched_name = next((name for name in names if _contains_person(text, name)), None)
        if matched_name:
            item["watch_person"] = matched_name
            item["leader"] = matched_name
            item["is_leader"] = True
            item["is_leader_watch"] = True
            item["leader_priority"] = priorities.get(matched_name, 0)
            watch_candidates += 1
            if _direct_interview_signal(item):
                item["_named_leader_interview"] = True
                item["leader_watch_protected"] = True
                matched += 1
            elif _leader_activity_signal(item):
                item["leader_activity_signal"] = True
                item["leader_watch_protected"] = True
                protected += 1
    print(f"[Leader Identity Recovery] verified_interviews={matched} | activity_protected={protected} | watchlist_candidates={watch_candidates}", flush=True)
    return items

def _is_protected_leader_interview(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if not leader or not (item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("_named_leader_interview")):
        return False
    return has_interview_evidence(item)

def _is_protected_leader_activity(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    return bool(leader and (item.get("is_leader_watch") or item.get("leader_watch_protected")) and _leader_activity_signal(item))

def _is_education(item):
    return str(item.get("content_type") or "").lower() in {"education", "educational"}

def _publication_text_within_limit(post):
    return len(str(post or "")) <= TELEGRAM_SAFE_TEXT_LIMIT

def _persist_item_success(item, seen_hashes, seen_signatures, source_history):
    mark_as_seen(item, seen_hashes, seen_signatures, source_history)

def _select_editorial_default(items, *, max_posts, max_per_source, max_per_type, policy):
    return select_regular_portfolio(items, max_posts=max_posts, max_per_source=max_per_source, max_per_type=max_per_type, recent_source_counts={}, contract=policy, mission_aware=True, strict_relevance=True)

def _split_protected(items, max_protected=2):
    candidates, regular = [], []
    for raw in items:
        item = dict(raw)
        if _is_protected_leader_interview(item) or _is_protected_leader_activity(item):
            item["protected_content"] = True
            item["protected_reason"] = "leader_interview_or_activity"
            item["_ai_link"] = True
            item["leader_watch_protected"] = True
            item["leader_source_authority"] = _leader_source_authority(item)
            candidates.append(item)
        else:
            regular.append(item)
    candidates.sort(key=lambda x: (
        int(x.get("leader_priority", 0) or 0),
        int(x.get("leader_source_authority", _leader_source_authority(x)) or 0),
        1 if _is_protected_leader_interview(x) else 0,
        0 if str(x.get("content_type") or "").lower() == "product_news" else 1,
        float(x.get("editorial_score", 0) or 0),
        str(x.get("published", "")),
    ), reverse=True)
    selected = candidates[:max(0, int(max_protected))]
    for item in selected:
        item["protected_slot"] = True
    regular.extend(candidates[len(selected):])
    return selected, regular

def _publication_summary_budget(items, max_posts, policy):
    buffer = max(0, int(policy.get("replacement_buffer", 3) or 3))
    protected = [x for x in items if x.get("protected_slot") or x.get("protected_content")]
    normal = [x for x in items if x not in protected]
    eligible_protected = [x for x in protected if float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0) >= PROTECTED_SUMMARY_SCORE_FLOOR]
    normal_window = max_posts + buffer
    bounded = eligible_protected[:max_posts] + normal[:normal_window]
    print(f"[Publication Summary Budget] input={len(items)} protected={len(eligible_protected)} normal_window={normal_window} output={len(bounded)} normal_limit={normal_window} replacement_buffer={buffer} score_floor={NORMAL_SCORE_FLOOR}", flush=True)
    return bounded

def _refill_after_late_dedup(selected, editorial_pool, select_editorial_fn, max_posts, max_per_source, max_per_type, policy, seen_hashes, runtime_selection_cap=None, *, cap=None):
    if runtime_selection_cap is None:
        runtime_selection_cap = cap if cap is not None else max_posts + int(policy.get("leader_protected_max", 2) or 2)
    target = min(runtime_selection_cap, max_posts + int(policy.get("leader_protected_max", 2) or 2))
    selected = filter_new_items(selected, seen_hashes)
    existing = {str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) for x in selected}
    pool = [x for x in editorial_pool if not x.get("protected_content") and not x.get("protected_slot") and str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) not in existing]
    pool = filter_new_items(pool, seen_hashes)
    while len(selected) < target and pool:
        extra = select_editorial_fn(pool, max_posts=1, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
        if not extra:
            break
        candidate = extra[0]
        selected.append(candidate)
        identity = str(candidate.get("canonical_url") or candidate.get("link") or candidate.get("url") or candidate.get("title") or id(candidate))
        pool = [x for x in pool if str(x.get("canonical_url") or x.get("link") or x.get("url") or x.get("title") or id(x)) != identity]
    return unique_candidates(selected)

def _safe_summarize(item, summarize_fn):
    """Isolate recoverable provider failures at candidate boundary; never fabricate a summary."""
    try:
        return summarize_fn(item)
    except (QuotaExceeded, TimeoutError, requests.exceptions.RequestException) as exc:
        identity = _publication_identity(item)
        print(f"[Editorial Gate] provider failure isolated candidate={identity[:120]} exception={type(exc).__name__}: {exc}", flush=True)
        item["_publication_blocked"] = True
        item["_summary_provider_failure"] = type(exc).__name__
        return None

def _summarize_selected(items, summarize_fn):
    workers = max(1, int(os.getenv("RADAR_SUMMARY_WORKERS", "1") or 1))
    if workers == 1 or len(items) <= 1:
        return [_safe_summarize(item, summarize_fn) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as executor:
        return list(executor.map(lambda item: _safe_summarize(item, summarize_fn), items))

def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):
    from src.unified_editorial_selection import load_editorial_contract

    contract = load_editorial_contract()
    from src.dedup import load_source_history
    from src.mission_coverage_priority import annotate_recovery_candidates

    try:
        source_history = load_source_history()
    except Exception as exc:
        logger.warning("Mission coverage history unavailable: %s", exc, exc_info=True)
        source_history = []
    editorial_pool = annotate_recovery_candidates(editorial_pool, source_history, contract)

    def _area(item):
        raw = str(item.get("mission_area") or item.get("category") or "").strip().casefold()
        return {"ai": "ai_core", "quantum": "convergence", "genetics": "convergence", "robotics": "convergence", "humanoid": "convergence", "bio": "convergence", "bci": "convergence", "mind": "mind_cognition", "future": "future_governance"}.get(raw, raw)

    selected_ids = {_publication_identity(x) for x in selected}

    def _score_ok(item):
        try:
            score = float(item.get("final_editorial_score", item.get("editorial_score", 0)) or 0)
        except (TypeError, ValueError):
            score = 0.0
        return score >= NORMAL_SCORE_FLOOR and not item.get("_publication_blocked")

    specs = [
        ("ai_core", int(contract.get("ai_core_target_min", 0) or 0)),
        ("convergence", int(contract.get("convergence_target", 0) or 0)),
    ]
    mind_target = int(contract.get("mind_cognition_target", 0) or 0)
    specs.append(("mind_cognition", mind_target) if mind_target > 0 else ("legacy_mind_future", int(contract.get("mind_future_target", 0) or 0)))

    missing = []
    for area, count in specs:
        if count <= 0:
            continue
        allowed = {"mind_cognition", "future_governance"} if area == "legacy_mind_future" else {area}
        covered = sum(1 for x in selected if _area(x) in allowed and _score_ok(x))
        missing.extend([allowed] * max(0, count - covered))

    if not missing:
        print("[Mission Coverage Recovery] no exact mission lane missing; recovery=0", flush=True)
        return []

    pool = [x for x in editorial_pool if _publication_identity(x) not in selected_ids and not x.get("_publication_blocked")]
    recovered, attempts = [], 0
    attempt_limit = max(1, int(policy.get("replacement_buffer", 3) or 3))

    for allowed_areas in missing:
        if attempts >= attempt_limit:
            break
        area_pool = [x for x in pool if _area(x) in allowed_areas]
        while area_pool and attempts < attempt_limit:
            attempts += 1
            chosen = select_editorial_fn(
                area_pool,
                max_posts=1,
                max_per_source=max_per_source,
                max_per_type=max_per_type,
                policy=policy,
            )
            if not chosen:
                break
            candidate = chosen[0]
            identity = _publication_identity(candidate)
            pool = [x for x in pool if _publication_identity(x) != identity]
            area_pool = [x for x in area_pool if _publication_identity(x) != identity]
            if not _score_ok(candidate):
                print(
                    f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=below_score_floor",
                    flush=True,
                )
                continue
            summary = _safe_summarize(candidate, summarize_fn)
            if not summary:
                print(
                    f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=failed",
                    flush=True,
                )
                continue
            candidate.update(summary)
            candidate["_mission_recovery"] = True
            recovered.append((candidate, summary))
            print(
                f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} title={str(candidate.get('title',''))[:120]} status=recovered",
                flush=True,
            )
            break

    print(
        f"[Mission Coverage Recovery] missing_lanes={len(missing)} attempts={attempts} recovered={len(recovered)} status={'ok' if len(recovered) >= len(missing) else 'unmet'}",
        flush=True,
    )
    return recovered

def main(hooks=None):
    configure_logging()
    hooks = dict(hooks or {}); select_editorial_fn = hooks.get("select_editorial", _select_editorial_default); split_protected_fn = hooks.get("split_protected", _split_protected); summarize_fn = hooks.get("summarize_item", summarize_item); format_fn = hooks.get("format_post", format_post); resolve_image_fn = hooks.get("resolve_source_image", resolve_source_image); deliver_fn = hooks.get("send_to_telegram_safe", send_to_telegram_safe); persist_fn = hooks.get("persist_item_success", _persist_item_success)
    config = load_yaml(CONFIG_PATH); leader_config = load_yaml(LEADER_CONFIG_PATH); selection = load_yaml(SELECTION_POLICY_PATH).get("selection", {}); policy = load_yaml(SELECTION_POLICY_PATH).get("editorial", {}); categories = config["categories"]; max_posts = int(selection.get("max_posts", 4)); max_per_source = int(selection.get("max_items_per_source", 2)); max_per_type = int(selection.get("max_items_per_content_type", 2)); leader_protected_max = int(policy.get("leader_protected_max", 2)); replacement_buffer = max(0, int(selection.get("replacement_buffer", 0) or 0)); runtime_selection_cap = leader_protected_max + max_posts + replacement_buffer; bridge_keywords = config.get("ai_bridge_keywords", []); story_threshold = float(selection.get("story_similarity_threshold", 0.45)); leader_people, leader_priorities = _leader_people(leader_config)
    youtube_channels = _merge_unique_dicts(config.get("youtube_channels", []), leader_config.get("youtube_channels", []), key="name"); leader_channel_names = {x.get("name") for x in leader_config.get("youtube_channels", [])}; base_youtube_channels = [x for x in youtube_channels if x.get("name") not in leader_channel_names]; leader_youtube_channels = [x for x in youtube_channels if x.get("name") in leader_channel_names]; base_queries = list(config.get("google_news_queries", [])); leader_queries = list(leader_config.get("google_news_queries", []))
    print("[1/7] Discovery: RSS / university / scientific / specialist sources"); rss_items = fetch_rss_items(config["rss_sources"], categories); print(f"RSS items: {len(rss_items)}")
    print("[2/7] Discovery: YouTube / interviews / podcasts / lectures"); base_youtube = fetch_youtube_items(base_youtube_channels, max_age_hours=72, ai_bridge_keywords=bridge_keywords); leader_youtube = _mark_leader_items(fetch_youtube_items(leader_youtube_channels, max_age_hours=720, ai_bridge_keywords=bridge_keywords)); youtube_items = base_youtube + leader_youtube; print(f"YouTube items: {len(youtube_items)} | leader-channel items: {len(leader_youtube)}")
    print("[3/7] Discovery: Google News + Leader Watchlist"); base_news = fetch_google_news_items(base_queries, max_age_hours=36, max_workers=4); leader_news = _mark_leader_items(fetch_google_news_items(leader_queries, max_age_hours=720, max_workers=1, inter_query_delay=0.35)); news_items = base_news + leader_news; print(f"Google News items: {len(news_items)} | leader candidates: {len(leader_news)}")
    all_items = rss_items + youtube_items + news_items; print(f"Raw total: {len(all_items)}"); all_items = _annotate_named_leader_interviews(all_items, leader_people, leader_priorities); seen_hashes, seen_signatures = load_seen(); source_history = load_source_history(); new_items = filter_new_items(all_items, seen_hashes); print(f"After link dedup: {len(new_items)}")
    protected_items, regular_items = split_protected_fn(new_items, max_protected=leader_protected_max); print(f"[Protected Leader Watch] selected={len(protected_items)} max={leader_protected_max} | regular_pool={len(regular_items)}"); print("[4/7] AI-first relevance gate (regular pool only)"); regular_items = filter_ai_relevance(regular_items, bridge_keywords); print("[5/7] Story clustering and canonical-source selection"); regular_enriched = enrich_items(regular_items, leader_priorities, source_history, policy); regular_enriched = enrich_signal_items(regular_enriched); _apply_signal_ranking(regular_enriched); regular_enriched.sort(key=lambda x: (x.get("editorial_score", 0), x.get("signal_score", 0)), reverse=True); leader_before, regular_before = len([x for x in regular_enriched if x.get("is_leader") or x.get("leader_signal")]), len([x for x in regular_enriched if not (x.get("is_leader") or x.get("leader_signal"))])
    editorial_pool = gate_story_candidates(protected_items, [x for x in regular_enriched if x.get("is_leader") or x.get("leader_signal")], [x for x in regular_enriched if not (x.get("is_leader") or x.get("leader_signal"))], seen_signatures, threshold=story_threshold); editorial_pool = sorted(editorial_pool, key=lambda x: (x.get("editorial_score", 0), x.get("signal_score", 0)), reverse=True); leader_after = sum(1 for x in editorial_pool if x.get("is_leader") or x.get("leader_signal")); regular_after = sum(1 for x in editorial_pool if not (x.get("is_leader") or x.get("leader_signal"))); protected_after = sum(1 for x in editorial_pool if x.get("protected_content")); print(f"[Story Gate] leaders={leader_before}->{leader_after} | regular={regular_before}->{regular_after} | protected={protected_after} | final stories={len(editorial_pool)}")
    selected_regular = select_editorial_fn(editorial_pool, max_posts=max_posts, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy); protected_candidates = [x for x in editorial_pool if x.get("protected_content")]; protected_selected = sorted(protected_candidates, key=lambda x: (int(x.get("leader_priority", 0) or 0), int(x.get("leader_source_authority", 0) or 0), 1 if _direct_interview_signal(x) else 0, x.get("published", "")), reverse=True)[:leader_protected_max]
    selected = unique_candidates(protected_selected + selected_regular); print(f"[Selection Guard] protected={len(protected_selected)} selected_unique={len(selected)} cap={runtime_selection_cap} normal_capacity={max_posts} replacement_buffer={replacement_buffer}", flush=True); selected = _refill_after_late_dedup(selected, editorial_pool, select_editorial_fn, max_posts, max_per_source, max_per_type, policy, seen_hashes, runtime_selection_cap)
    selected = _publication_summary_budget(selected, max_posts, policy)
    if not selected: print("[Final Publication Guard] no publishable items remain", flush=True); save_seen(seen_hashes, seen_signatures, source_history); print("Posts sent: 0/0"); return
    print("[6/7] AI processing / summarization"); summaries = _summarize_selected(selected, summarize_fn)
    for item, summary in zip(selected, summaries):
        if summary: item.update(summary)
        else: item["_publication_blocked"] = True; print(f"[Editorial Gate] skipped candidate: {str(item.get('title',''))[:120]}", flush=True)
        item["source_image"] = resolve_image_fn(item)
    mission_recovery = _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes)
    for candidate, _summary in mission_recovery: candidate["source_image"] = resolve_image_fn(candidate); selected.append(candidate)
    print("[7/7] Telegram publication"); sent = 0
    initial_selected_count = len(selected)
    publication_attempted = {_publication_identity(item) for item in selected}
    lazy_replacements = 0
    replacement_limit = max(0, int(policy.get("replacement_buffer", replacement_buffer) or replacement_buffer))
    publication_queue = list(selected)
    next_candidate_index = 0

    def _candidate_identity(item):
        return str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or id(item))

    def _prepare_lazy_replacement():
        nonlocal lazy_replacements, next_candidate_index
        if lazy_replacements >= replacement_limit:
            return None
        while next_candidate_index < len(editorial_pool):
            candidate = editorial_pool[next_candidate_index]; next_candidate_index += 1; identity = _candidate_identity(candidate)
            if identity in publication_attempted: continue
            score = float(candidate.get("final_editorial_score", candidate.get("editorial_score", 0)) or 0)
            if candidate.get("protected_content"):
                if score < PROTECTED_SUMMARY_SCORE_FLOOR: continue
            else:
                normal_rank = candidate.get("normal_period_rank")
                try: normal_rank = int(normal_rank)
                except (TypeError, ValueError): continue
                if normal_rank > int(policy.get("candidate_window", 6) or 6) or score < NORMAL_SCORE_FLOOR: continue
            candidate = dict(candidate); summary = _safe_summarize(candidate, summarize_fn)
            if not summary:
                print(f"[Publication Lazy Refill] summary blocked; skipping candidate: {str(candidate.get('title',''))[:120]}", flush=True); continue
            candidate.update(summary); candidate["source_image"] = resolve_image_fn(candidate); publication_attempted.add(identity); lazy_replacements += 1
            print(f"[Publication Lazy Refill] prepared replacement={lazy_replacements}/{replacement_limit} normal_rank={candidate.get('normal_period_rank')} score={candidate.get('final_editorial_score', candidate.get('editorial_score', 0))} title={str(candidate.get('title',''))[:120]}", flush=True)
            return candidate
        return None

    queue_index = 0
    while queue_index < len(publication_queue):
        item = publication_queue[queue_index]; queue_index += 1
        if item.get("_publication_blocked"): continue
        try:
            source_name = str(item.get("source") or item.get("source_name") or "منبع"); link = str(item.get("link") or item.get("url") or ""); post = format_fn(item, source_name, link, is_video=str(item.get("source_type") or "").lower() in {"youtube", "video"}, published=item.get("published", ""), content_type=item.get("content_type", "news"), source_tier=item.get("source_tier", 3), source_type=item.get("source_type", "news"), leader=item.get("leader") or item.get("watch_person") or "")
            if not _publication_text_within_limit(post):
                replacement = _prepare_lazy_replacement()
                if replacement is not None: publication_queue.append(replacement)
                continue
            result = deliver_fn(post, image_url=str(item.get("source_image") or ""), source_link=link)
            if hasattr(result, "status"):
                status_value = getattr(result.status, "value", str(result.status))
                if status_value == "delivered": sent += 1; persist_fn(item, seen_hashes, seen_signatures, source_history); continue
                if status_value in {"policy_blocked", "rejected", "duplicate"}:
                    print(f"[Publication Contract] candidate rejected reason={getattr(result, 'reason', '')}; continuing to next ranked candidate", flush=True)
                    replacement = _prepare_lazy_replacement()
                    if replacement is not None: publication_queue.append(replacement)
                    continue
                raise RuntimeError(f"Telegram transport failure: {getattr(result, 'reason', 'unknown')}")
            if not result: raise RuntimeError("Telegram delivery returned false")
            sent += 1; persist_fn(item, seen_hashes, seen_signatures, source_history)
        except Exception as exc:
            logger.error("Telegram send failed for %s: %s", item.get("title", "")[:100], exc, exc_info=True)
            print(f"[ERROR] Telegram send failed for {item.get('title','')[:100]}: {exc}", flush=True)
    print(f"[Publication Lazy Refill] initial={initial_selected_count} lazy_replacements={lazy_replacements} final_attempt_queue={len(publication_queue)}", flush=True)
    save_seen(seen_hashes, seen_signatures, source_history); print(f"Posts sent: {sent}/{len(publication_queue)}")

if __name__ == "__main__":
    try:
        main()
    except StateCorruptionError as exc:
        logger.error("[STATE] %s", exc, exc_info=True)
        raise SystemExit(1) from exc
