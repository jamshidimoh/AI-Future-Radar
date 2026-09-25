# ruff: noqa: I001
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from src.dedup import filter_new_items, load_seen, load_source_history, mark_as_seen, save_seen
from src.editorial import enrich_items, filter_ai_relevance
from src.editorial_quality_policy import NORMAL_SCORE_FLOOR as CANONICAL_NORMAL_SCORE_FLOOR
from src.fetch_google_news import fetch_google_news_items
from src.fetch_rss import fetch_rss_items
from src.fetch_youtube import fetch_youtube_items
from src.interview_evidence import has_interview_evidence
from src.llm_router_light import QuotaExceeded
from src.logging_setup import configure_logging
from src.mission_selector import _source_tier
from production_entrypoint import _people_bootstrap_batch
from src.people_watch import (
    bootstrap_candidates,
    build_bootstrap_state,
    deduplicate_people_signals,
    identity as people_identity,
    load_people_watchlist,
    now_iso,
    post_bootstrap_candidates,
)
from src.protected_editorial_lane import MIND_IDEAS_VOICES_SCORE_FLOOR, mind_ideas_voices_score
from src.publication_contract import unique_candidates
from src.rejection_telemetry import build_event, emit
from src.send_telegram import format_post, resolve_source_image, send_to_telegram_safe
from src.signal_engine import enrich_signal_items
from src.state_io import StateCorruptionError
from src.story_gate import gate_story_candidates
from src.summarize import summarize_item
from src.unified_editorial_selection import mission_area, select_regular_portfolio
from src.voices_perspectives_lane import choose_voices_candidate

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
LEADER_CONFIG_PATH = ROOT / "config" / "leader_watchlist.yaml"
SELECTION_POLICY_PATH = ROOT / "config" / "selection_policy.yaml"
TELEGRAM_SAFE_TEXT_LIMIT = 3900
PROTECTED_SUMMARY_SCORE_FLOOR = 60.0
NORMAL_SCORE_FLOOR = CANONICAL_NORMAL_SCORE_FLOOR
MAX_MIND_IDEAS_VOICES_PER_PERIOD = 2
PEOPLE_BOOTSTRAP_RESULT = None


def _is_mind_ideas_voices(item: dict) -> bool:
    return bool(
        item.get("mind_lane_selected")
        or item.get("protected_editorial_lane") == "mind_ideas_voices"
        or item.get("lane") == "mind_ideas_voices"
    )


def _is_voices_perspectives(item: dict) -> bool:
    return bool(
        item.get("voices_perspectives_lane_selected")
        or item.get("editorial_lane") == "voices_perspectives"
    )


def _publication_identity(item: dict) -> str:
    return str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or id(item))


def _runtime_telemetry_event(item: dict, *, stage: str, decision: str, reason_code: str, details=None, attempt=None) -> None:
    try:
        identity = _publication_identity(item)
        trace_id = __import__("hashlib").sha1(identity.encode("utf-8", errors="ignore")).hexdigest()[:16]
        run_id = str(os.getenv("GITHUB_RUN_ID") or os.getenv("RADAR_RUN_ID") or "local")
        raw_run_number = os.getenv("GITHUB_RUN_NUMBER") or os.getenv("RADAR_RUN_NUMBER")
        try:
            run_number = int(raw_run_number) if raw_run_number is not None else None
        except (TypeError, ValueError):
            run_number = None
        path = Path(os.getenv("RADAR_REJECTION_TRACE_PATH", "artifacts/rejection_trace/rejection_trace.jsonl"))
        emit(
            build_event(
                run_id=run_id,
                run_number=run_number,
                trace_id=trace_id,
                item_id=identity,
                stage=stage,
                decision=decision,
                reason_code=reason_code,
                item=item,
                details=details,
                attempt=attempt,
                replacement_eligible=item.get("replacement_eligible"),
            ),
            path,
        )
    except Exception:
        return


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


def _is_technical_trend(item):
    return bool(item.get("technical_trend_lane_selected") or item.get("editorial_lane") == "technical_trend")


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
    people = [x for x in items if x.get("people_lane")]
    people_ids = {id(x) for x in people}
    mind = [x for x in items if id(x) not in people_ids and _is_mind_ideas_voices(x)][:MAX_MIND_IDEAS_VOICES_PER_PERIOD]
    mind_ids = {id(x) for x in mind}
    voices = [x for x in items if _is_voices_perspectives(x)]
    voices = voices[:1]
    voices_ids = {id(x) for x in voices}
    technical = [x for x in items if _is_technical_trend(x)]
    technical = technical[:1]
    technical_ids = {id(x) for x in technical}
    protected = [
        x for x in items
        if (x.get("protected_slot") or x.get("protected_content"))
        and id(x) not in people_ids
        and id(x) not in mind_ids
        and id(x) not in voices_ids
        and id(x) not in technical_ids
    ]
    special_ids = mind_ids | voices_ids | technical_ids
    normal = [
        x for x in items
        if id(x) not in people_ids and id(x) not in special_ids and x not in protected
    ]
    eligible_protected = [
        x for x in protected
        if float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0) >= PROTECTED_SUMMARY_SCORE_FLOOR
    ]
    normal_window = max_posts + buffer
    # Every independent lane that survived editorial selection must survive the
    # summary budget too. Otherwise the lane can be correctly selected and then
    # silently disappear before Telegram publication.
    bounded = (
        eligible_protected[:max_posts]
        + normal[:normal_window]
        + technical
        + mind
        + voices
        + people
    )
    print(
        f"[Publication Summary Budget] input={len(items)} protected={len(eligible_protected)} "
        f"normal={len(normal[:normal_window])} technical_trend={len(technical)} "
        f"mind_ideas_voices={len(mind)} voices_perspectives={len(voices)} "
        f"normal_window={normal_window} output={len(bounded)} normal_limit={normal_window} "
        f"mind_limit={MAX_MIND_IDEAS_VOICES_PER_PERIOD} voices_limit=1 replacement_buffer={buffer} "
        f"normal_score_floor={NORMAL_SCORE_FLOOR} special_lanes_score_floor=not_applied",
        flush=True,
    )
    return bounded


def _refill_after_late_dedup(selected, editorial_pool, select_editorial_fn, max_posts, max_per_source, max_per_type, policy, seen_hashes, runtime_selection_cap=None, *, cap=None, bootstrap_mode=False):
    if runtime_selection_cap is None:
        runtime_selection_cap = cap if cap is not None else max_posts + int(policy.get("leader_protected_max", 2) or 2) + MAX_MIND_IDEAS_VOICES_PER_PERIOD
    if bootstrap_mode:
        # Bootstrap selection already has explicit People batching plus the
        # independent special lanes. Never refill with normal-lane candidates.
        return selected
    target = min(runtime_selection_cap, max_posts + int(policy.get("leader_protected_max", 2) or 2) + MAX_MIND_IDEAS_VOICES_PER_PERIOD)
    people_selected = [x for x in selected if x.get("people_lane")]
    non_people_selected = [x for x in selected if not x.get("people_lane")]
    non_people_selected = filter_new_items(non_people_selected, seen_hashes)
    selected = people_selected + non_people_selected
    existing = {_publication_identity(x) for x in selected}
    pool = [x for x in editorial_pool if not x.get("people_lane") and not x.get("protected_content") and not x.get("protected_slot") and _publication_identity(x) not in existing]
    pool = filter_new_items(pool, seen_hashes)
    while len(selected) < target and pool:
        extra = select_editorial_fn(pool, max_posts=1, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
        if not extra:
            break
        candidate = extra[0]
        selected.append(candidate)
        identity = _publication_identity(candidate)
        pool = [x for x in pool if _publication_identity(x) != identity]
    return unique_candidates(selected)


def _safe_summarize(item, summarize_fn):
    """Isolate recoverable provider failures at candidate boundary; never fabricate a summary."""
    try:
        return summarize_fn(item)
    except (QuotaExceeded, TimeoutError, requests.exceptions.RequestException) as exc:
        identity = _publication_identity(item)
        reason_code = {
            QuotaExceeded: "provider_quota_exceeded",
            TimeoutError: "provider_timeout",
            requests.exceptions.RequestException: "provider_request_failure",
        }.get(type(exc), "provider_generation_failure")
        _runtime_telemetry_event(
            item,
            stage="summarization",
            decision="unavailable",
            reason_code=reason_code,
            details={"exception_type": type(exc).__name__, "exception": str(exc)[:500]},
        )
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


def _voice_lane_recovery(selected, editorial_pool, summarize_fn):
    """Refill the independent Expert Voice slot only when its selected item fails QA."""
    if any(_is_voices_perspectives(item) and not item.get("_publication_blocked") for item in selected):
        return []
    selected_ids = {_publication_identity(item) for item in selected}
    pool = [
        item for item in editorial_pool
        if _publication_identity(item) not in selected_ids
        and not item.get("_publication_blocked")
    ]
    candidate = (choose_voices_candidate(pool, existing_ids=set(), max_items=1) or [None])[0]
    if candidate is None:
        print("[Voice Lane Recovery] no independent expert candidate available", flush=True)
        return []
    summary = _safe_summarize(candidate, summarize_fn)
    if not summary:
        print(
            f"[Voice Lane Recovery] replacement failed title={str(candidate.get('title',''))[:120]}",
            flush=True,
        )
        return []
    candidate.update(summary)
    candidate["_voice_lane_recovery"] = True
    print(
        f"[Voice Lane Recovery] recovered rank={candidate.get('voices_period_rank')} "
        f"score={candidate.get('voices_perspectives_score')} "
        f"title={str(candidate.get('title',''))[:120]}",
        flush=True,
    )
    return [(candidate, summary)]


def _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes):
    from src.unified_editorial_selection import load_editorial_contract
    contract = load_editorial_contract()
    import src.llm_router_light as llm_router
    recovery_cooldowns_reset = llm_router.reset_recoverable_cooldowns()
    if recovery_cooldowns_reset:
        print(
            f"[Mission Coverage Recovery] retryable_provider_cooldowns_reset={recovery_cooldowns_reset}",
            flush=True,
        )
    from src.dedup import load_source_history
    from src.mission_coverage_priority import annotate_recovery_candidates
    try:
        source_history = load_source_history()
    except Exception as exc:
        logger.warning("Mission coverage history unavailable: %s", exc, exc_info=True)
        source_history = []
    editorial_pool = annotate_recovery_candidates(editorial_pool, source_history, contract)

    def _area(item):
        return mission_area(item)

    selected_ids = {_publication_identity(x) for x in selected}

    def _score_ok(item):
        if _is_mind_ideas_voices(item):
            if item.get("_publication_blocked"):
                return False
            try:
                score = float(item.get("mind_editorial_score", mind_ideas_voices_score(item)) or 0)
            except (TypeError, ValueError):
                score = 0.0
            return score >= MIND_IDEAS_VOICES_SCORE_FLOOR
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
    lane_attempt_limit = max(1, int(policy.get("replacement_buffer", 3) or 3))

    for allowed_areas in missing:
        lane_recovered = False
        lane_attempts = 0
        while lane_attempts < lane_attempt_limit:
            area_pool = [
                x for x in pool
                if _area(x) in allowed_areas
                and _publication_identity(x) not in selected_ids
            ]
            if not area_pool:
                print(
                    f"[Mission Coverage Recovery] area={','.join(sorted(allowed_areas))} "
                    f"status=no_candidate",
                    flush=True,
                )
                break

            # Select only from the exact mission-area pool. This prevents the
            # generic four-lane selector from redirecting a recovery attempt to
            # another mission area.
            chosen = select_regular_portfolio(
                area_pool,
                max_posts=1,
                max_per_source=max_per_source,
                max_per_type=max_per_type,
                recent_source_counts={},
                contract=contract,
                mission_aware=True,
                strict_relevance=True,
            )
            if not chosen:
                # Last-resort deterministic choice from the exact area, still
                # bounded to this lane and without relaxing score/QA gates.
                chosen = sorted(
                    area_pool,
                    key=lambda x: (
                        float(x.get("final_editorial_score", x.get("editorial_score", 0)) or 0),
                        float(x.get("signal_score", 0) or 0),
                        float(x.get("evidence_strength", 0) or 0),
                        str(x.get("published", "")),
                    ),
                    reverse=True,
                )[:1]

            candidate = chosen[0]
            identity = _publication_identity(candidate)
            pool = [x for x in pool if _publication_identity(x) != identity]
            lane_attempts += 1
            attempts += 1

            if not _score_ok(candidate):
                try:
                    score = float(candidate.get("final_editorial_score", candidate.get("editorial_score", 0)) or 0)
                except Exception:
                    score = 0.0
                if _is_mind_ideas_voices(candidate):
                    print(
                        f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} "
                        f"title={str(candidate.get('title',''))[:120]} "
                        f"status=independent_lane_not_score_gated",
                        flush=True,
                    )
                else:
                    reason_code = "protected_score_floor" if candidate.get("protected_content") else "normal_score_floor"
                    _runtime_telemetry_event(
                        candidate,
                        stage="selection",
                        decision="reject",
                        reason_code=reason_code,
                        details={
                            "score": score,
                            "floor": PROTECTED_SUMMARY_SCORE_FLOOR if candidate.get("protected_content") else NORMAL_SCORE_FLOOR,
                            "mission_area": _area(candidate),
                        },
                        attempt=attempts,
                    )
                    print(
                        f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} "
                        f"title={str(candidate.get('title',''))[:120]} status=below_score_floor",
                        flush=True,
                    )
                continue

            summary = _safe_summarize(candidate, summarize_fn)
            if not summary:
                _runtime_telemetry_event(
                    candidate,
                    stage="mission_recovery",
                    decision="reject",
                    reason_code="mission_recovery_candidate_failure",
                    details={"mission_area": _area(candidate), "attempt": attempts},
                    attempt=attempts,
                )
                print(
                    f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} "
                    f"title={str(candidate.get('title',''))[:120]} status=failed",
                    flush=True,
                )
                continue

            candidate.update(summary)
            candidate["_mission_recovery"] = True
            recovered.append((candidate, summary))
            lane_recovered = True
            print(
                f"[Mission Coverage Recovery] attempt={attempts} area={_area(candidate)} "
                f"title={str(candidate.get('title',''))[:120]} status=recovered",
                flush=True,
            )
            break

        if not lane_recovered:
            print(
                f"[Mission Coverage Recovery] lane={','.join(sorted(allowed_areas))} "
                f"status=unmet",
                flush=True,
            )

    recovery_status = "ok" if len(recovered) >= len(missing) else "unmet"
    if recovery_status == "unmet":
        _runtime_telemetry_event(
            {"title": "mission-coverage-recovery", "mission_area": "recovery", "source": "runtime"},
            stage="mission_recovery",
            decision="unmet",
            reason_code="mission_coverage_unmet",
            details={
                "missing_lanes": len(missing),
                "attempts": attempts,
                "recovered": len(recovered),
            },
        )
    print(
        f"[Mission Coverage Recovery] missing_lanes={len(missing)} attempts={attempts} "
        f"recovered={len(recovered)} status={recovery_status}",
        flush=True,
    )
    return recovered

def main(hooks=None):
    global PEOPLE_BOOTSTRAP_RESULT
    configure_logging()
    hooks = dict(hooks or {})
    select_editorial_fn = hooks.get("select_editorial", _select_editorial_default)
    split_protected_fn = hooks.get("split_protected", _split_protected)
    summarize_fn = hooks.get("summarize_item", summarize_item)
    format_fn = hooks.get("format_post", format_post)
    resolve_image_fn = hooks.get("resolve_source_image", resolve_source_image)
    deliver_fn = hooks.get("send_to_telegram_safe", send_to_telegram_safe)
    persist_fn = hooks.get("persist_item_success", _persist_item_success)
    config = load_yaml(CONFIG_PATH)
    leader_config = load_yaml(LEADER_CONFIG_PATH)
    people_watchlist = load_people_watchlist(LEADER_CONFIG_PATH)
    cadence_state_path = ROOT / "data" / "publication_state.json"
    try:
        import json
        cadence_snapshot = json.loads(cadence_state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        cadence_snapshot = {}
    people_state = cadence_snapshot.get("people_bootstrap", {}) if isinstance(cadence_snapshot, dict) else {}
    people_bootstrap_mode = str(people_state.get("status") or "").casefold() != "complete"
    people_bootstrap_at = str(people_state.get("bootstrap_at") or "").strip() or now_iso()
    selection = load_yaml(SELECTION_POLICY_PATH).get("selection", {})
    policy = load_yaml(SELECTION_POLICY_PATH).get("editorial", {})
    categories = config["categories"]
    max_posts = int(selection.get("max_posts", 4))
    max_per_source = int(selection.get("max_items_per_source", 2))
    max_per_type = int(selection.get("max_items_per_content_type", 2))
    leader_protected_max = int(policy.get("leader_protected_max", 2))
    replacement_buffer = max(0, int(selection.get("replacement_buffer", 0) or 0))
    runtime_selection_cap = leader_protected_max + max_posts + replacement_buffer + MAX_MIND_IDEAS_VOICES_PER_PERIOD
    bridge_keywords = config.get("ai_bridge_keywords", [])
    story_threshold = float(selection.get("story_similarity_threshold", 0.45))
    leader_people, leader_priorities = _leader_people(leader_config)
    youtube_channels = _merge_unique_dicts(config.get("youtube_channels", []), leader_config.get("youtube_channels", []), key="name")
    leader_channel_names = {x.get("name") for x in leader_config.get("youtube_channels", [])}
    base_youtube_channels = [x for x in youtube_channels if x.get("name") not in leader_channel_names]
    leader_youtube_channels = [x for x in youtube_channels if x.get("name") in leader_channel_names]
    base_queries = list(config.get("google_news_queries", []))
    leader_queries = list(leader_config.get("google_news_queries", []))
    print("[1/7] Discovery: RSS / university / scientific / specialist sources")
    rss_items = fetch_rss_items(config["rss_sources"], categories)
    print(f"RSS items: {len(rss_items)}")
    print("[2/7] Discovery: YouTube / interviews / podcasts / lectures")
    base_youtube = fetch_youtube_items(base_youtube_channels, max_age_hours=72, ai_bridge_keywords=bridge_keywords)
    leader_youtube = _mark_leader_items(fetch_youtube_items(leader_youtube_channels, max_age_hours=87600, ai_bridge_keywords=bridge_keywords))
    youtube_items = base_youtube + leader_youtube
    print(f"YouTube items: {len(youtube_items)} | leader-channel items: {len(leader_youtube)}")
    print("[3/7] Discovery: Google News + Leader Watchlist")
    base_news = fetch_google_news_items(base_queries, max_age_hours=36, max_workers=4)
    leader_news = _mark_leader_items(fetch_google_news_items(leader_queries, max_age_hours=87600, max_workers=3, inter_query_delay=0.0))
    news_items = base_news + leader_news
    print(f"Google News items: {len(news_items)} | leader candidates: {len(leader_news)}")
    all_items = rss_items + youtube_items + news_items
    print(f"Raw total: {len(all_items)}")
    all_items = _annotate_named_leader_interviews(all_items, leader_people, leader_priorities)
    seen_hashes, seen_signatures = load_seen()
    source_history = load_source_history()
    if people_bootstrap_mode:
        people_candidates = bootstrap_candidates(
            all_items,
            people_watchlist,
            previous_state=people_state,
            seen_hashes=seen_hashes,
        )
        baseline_people = set((people_state.get("baseline") or {}).keys()) if isinstance(people_state, dict) else set()
        discovered_people = {str(x.get("person_name") or x.get("watch_person") or "").strip() for x in people_candidates}
        discovered_people.discard("")
        planned_people = baseline_people | discovered_people
        print(f"[People Bootstrap] required=30 discovered_now={len(discovered_people)} baseline={len(baseline_people)} planned={len(planned_people)}")
        # Keep the full discovered set for baseline/state construction, but cap
        # actual Telegram publication to the canonical per-run People batch.
        people_publication_candidates = _people_bootstrap_batch(people_candidates)
        print(
            f"[People Bootstrap] publication_batch={len(people_publication_candidates)} "
            f"discovered_pool={len(people_candidates)}",
            flush=True,
        )
        # Bootstrap is progressive, not a global publication lock. Missing people
        # are retried on later runs, while every currently qualified signal can
        # still be published and the normal Radar lanes continue in parallel.
        if len(planned_people) != 30:
            PEOPLE_BOOTSTRAP_RESULT = build_bootstrap_state(
                bootstrap_at=people_bootstrap_at,
                candidates=people_candidates,
                delivered_people=[],
                status="in_progress",
                previous_state=people_state,
            )
            print(
                f"[People Bootstrap] partial baseline planned={len(planned_people)}/30; "
                "continuing with available People + normal lanes",
                flush=True,
            )
    else:
        people_publication_candidates = people_candidates
        people_candidates = post_bootstrap_candidates(
            all_items,
            people_watchlist,
            bootstrap_at=people_bootstrap_at,
            seen_hashes=seen_hashes,
        )
        people_candidates = deduplicate_people_signals(people_candidates, seen_signatures=seen_signatures)
        people_publication_candidates = people_candidates
        print(f"[People Signal] bootstrap_at={people_bootstrap_at} candidates_after_dedup={len(people_candidates)}")
    # Global seen/event dedup remains for the normal Radar lanes only. People
    # must reach its own per-person event clustering first.
    new_items = filter_new_items(all_items, seen_hashes)
    people_ids = {people_identity(x) for x in people_candidates if people_identity(x)}

    normal_input_items = [x for x in new_items if people_identity(x) not in people_ids]
    protected_items, regular_items = split_protected_fn(normal_input_items, max_protected=leader_protected_max)
    print(f"[Protected Leader Watch] selected={len(protected_items)} max={leader_protected_max} | regular_pool={len(regular_items)}")
    print("[4/7] AI-first relevance gate (regular pool only)")
    regular_items = filter_ai_relevance(regular_items, bridge_keywords)
    print("[5/7] Story clustering and canonical-source selection")
    regular_enriched = enrich_items(regular_items, leader_priorities, source_history, policy)
    regular_enriched = enrich_signal_items(regular_enriched)
    _apply_signal_ranking(regular_enriched)
    regular_enriched.sort(key=lambda x: (x.get("editorial_score", 0), x.get("signal_score", 0)), reverse=True)
    leader_before = len([x for x in regular_enriched if x.get("is_leader") or x.get("leader_signal")])
    regular_before = len([x for x in regular_enriched if not (x.get("is_leader") or x.get("leader_signal"))])
    editorial_pool = gate_story_candidates(protected_items, [x for x in regular_enriched if x.get("is_leader") or x.get("leader_signal")], [x for x in regular_enriched if not (x.get("is_leader") or x.get("leader_signal"))], seen_signatures, threshold=story_threshold)
    editorial_pool = sorted(editorial_pool, key=lambda x: (x.get("editorial_score", 0), x.get("signal_score", 0)), reverse=True)
    leader_after = sum(1 for x in editorial_pool if x.get("is_leader") or x.get("leader_signal"))
    regular_after = len([x for x in editorial_pool if not (x.get("is_leader") or x.get("leader_signal"))])
    protected_after = sum(1 for x in editorial_pool if x.get("protected_content"))
    print(f"[Story Gate] leaders={leader_before}->{leader_after} | regular={regular_before}->{regular_after} | protected={protected_after} | final stories={len(editorial_pool)}")
    if people_bootstrap_mode:
        print("[People Bootstrap] progressive mode: normal/special lanes remain enabled")
    if people_bootstrap_mode:
        # People bootstrap candidates are an independent protected input to the
        # production selector; they must reach the selector before the batch cap.
        editorial_pool = unique_candidates(list(people_publication_candidates) + list(editorial_pool))
        print(
            f"[People Bootstrap] selector_input={len(people_publication_candidates)} "
            f"discovered_pool={len(people_candidates)} people_candidates_added=true",
            flush=True,
        )
    selected_regular = select_editorial_fn(editorial_pool, max_posts=max_posts, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy)
    selected_regular = unique_candidates(selected_regular + people_publication_candidates)
    protected_candidates = [] if people_bootstrap_mode else [x for x in editorial_pool if x.get("protected_content")]
    protected_selected = (
        []
        if people_bootstrap_mode
        else sorted(
            protected_candidates,
            key=lambda x: (
                int(x.get("leader_priority", 0) or 0),
                int(x.get("leader_source_authority", 0) or 0),
                1 if _direct_interview_signal(x) else 0,
                x.get("published", ""),
            ),
            reverse=True,
        )[:leader_protected_max]
    )
    selected = unique_candidates(protected_selected + selected_regular)
    people_selected_count = sum(1 for x in selected if x.get("people_lane"))
    people_cap_label = "2" if people_bootstrap_mode else "post_bootstrap"
    print(
        f"[Selection Guard] protected={len(protected_selected)} selected_unique={len(selected)} "
        f"cap={runtime_selection_cap} normal_capacity={max_posts} replacement_buffer={replacement_buffer} "
        f"mind_quota={MAX_MIND_IDEAS_VOICES_PER_PERIOD} "
        f"people={people_selected_count} people_cap={people_cap_label}",
        flush=True,
    )
    selected = _refill_after_late_dedup(
        selected,
        editorial_pool,
        select_editorial_fn,
        max_posts,
        max_per_source,
        max_per_type,
        policy,
        seen_hashes,
        runtime_selection_cap,
        bootstrap_mode=people_bootstrap_mode,
    )
    selected = _publication_summary_budget(selected, max_posts, policy)
    if not selected:
        print("[Final Publication Guard] no publishable items remain", flush=True)
        save_seen(seen_hashes, seen_signatures, source_history)
        print("Posts sent: 0/0")
        return
    print("[6/7] AI processing / summarization")
    summaries = _summarize_selected(selected, summarize_fn)
    for item, summary in zip(selected, summaries):
        if summary:
            item.update(summary)
        else:
            item["_publication_blocked"] = True
            print(f"[Editorial Gate] skipped candidate: {str(item.get('title',''))[:120]}", flush=True)
        item["source_image"] = resolve_image_fn(item)
    voice_recovery = _voice_lane_recovery(selected, editorial_pool, summarize_fn)
    for candidate, _summary in voice_recovery:
        candidate["source_image"] = resolve_source_image(candidate)
        selected.append(candidate)

    mission_recovery = _mission_coverage_recovery(selected, editorial_pool, select_editorial_fn, summarize_fn, max_per_source, max_per_type, policy, seen_hashes)
    for candidate, _summary in mission_recovery:
        candidate["source_image"] = resolve_source_image(candidate)
        selected.append(candidate)
    print("[7/7] Telegram publication")
    sent = 0
    people_sent = 0
    delivered_people: list[str] = []
    initial_selected_count = len(selected)
    publication_attempted = {_publication_identity(item) for item in selected}
    lazy_replacements = 0
    replacement_limit = max(0, int(policy.get("replacement_buffer", replacement_buffer) or replacement_buffer))
    publication_queue = list(selected)
    next_candidate_index = 0

    def _candidate_identity(item):
        return _publication_identity(item)

    def _prepare_lazy_replacement():
        nonlocal lazy_replacements, next_candidate_index
        if lazy_replacements >= replacement_limit:
            return None
        while next_candidate_index < len(editorial_pool):
            candidate = editorial_pool[next_candidate_index]
            next_candidate_index += 1
            identity = _candidate_identity(candidate)
            if identity in publication_attempted:
                continue
            mind = _is_mind_ideas_voices(candidate)
            raw_score = (
                candidate.get("mind_editorial_score")
                if mind
                else candidate.get("final_editorial_score", candidate.get("editorial_score", 0))
            )
            score = float(
                raw_score if raw_score is not None else mind_ideas_voices_score(candidate) if mind else 0
            )
            if mind and "mind_editorial_score" not in candidate:
                score = mind_ideas_voices_score(candidate)
            if mind and score < MIND_IDEAS_VOICES_SCORE_FLOOR:
                continue
            if not mind:
                if candidate.get("protected_content"):
                    if score < PROTECTED_SUMMARY_SCORE_FLOOR:
                        continue
                else:
                    normal_rank = candidate.get("normal_period_rank")
                    try:
                        normal_rank = int(normal_rank)
                    except (TypeError, ValueError):
                        continue
                    if normal_rank > int(policy.get("candidate_window", 6) or 6) or score < NORMAL_SCORE_FLOOR:
                        continue
            candidate = dict(candidate)
            summary = _safe_summarize(candidate, summarize_fn)
            if not summary:
                print(f"[Publication Lazy Refill] summary blocked; skipping candidate: {str(candidate.get('title',''))[:120]}", flush=True)
                continue
            candidate.update(summary)
            candidate["source_image"] = resolve_source_image(candidate)
            publication_attempted.add(identity)
            lazy_replacements += 1
            lane = "mind_ideas_voices" if mind else ("protected" if candidate.get("protected_content") else "normal")
            print(f"[Publication Lazy Refill] prepared replacement={lazy_replacements}/{replacement_limit} lane={lane} normal_rank={candidate.get('normal_period_rank')} mind_rank={candidate.get('mind_period_rank')} score={score}", flush=True)
            return candidate
        return None

    queue_index = 0
    while queue_index < len(publication_queue):
        item = publication_queue[queue_index]
        queue_index += 1
        if item.get("_publication_blocked"):
            continue
        try:
            source_name = str(item.get("source") or item.get("source_name") or "منبع")
            link = str(item.get("link") or item.get("url") or "")
            post = format_fn(item, source_name, link, is_video=str(item.get("source_type") or "").lower() in {"youtube", "video"}, published=item.get("published", ""), content_type=item.get("content_type", "news"), source_tier=item.get("source_tier", 3), source_type=item.get("source_type", "news"), leader=item.get("leader") or item.get("watch_person") or "")
            if not _publication_text_within_limit(post):
                replacement = _prepare_lazy_replacement()
                if replacement is not None:
                    publication_queue.append(replacement)
                continue
            result = deliver_fn(post, image_url=str(item.get("source_image") or ""), source_link=link)
            if hasattr(result, "status"):
                status_value = getattr(result.status, "value", str(result.status))
                if status_value == "delivered":
                    sent += 1
                    if item.get("people_lane"):
                        people_sent += 1
                        delivered_people.append(str(item.get("person_name") or item.get("watch_person") or "").strip())
                    persist_fn(item, seen_hashes, seen_signatures, source_history)
                    continue
                if status_value in {"policy_blocked", "rejected", "duplicate"}:
                    print(f"[Publication Contract] candidate rejected reason={getattr(result, 'reason', '')}; continuing to next ranked candidate", flush=True)
                    replacement = _prepare_lazy_replacement()
                    if replacement is not None:
                        publication_queue.append(replacement)
                    continue
                raise RuntimeError(f"Telegram transport failure: {getattr(result, 'reason', 'unknown')}")
            if not result:
                raise RuntimeError("Telegram delivery returned false")
            sent += 1
            if item.get("people_lane"):
                people_sent += 1
                delivered_people.append(str(item.get("person_name") or item.get("watch_person") or "").strip())
            persist_fn(item, seen_hashes, seen_signatures, source_history)
        except Exception as exc:
            logger.error("Telegram send failed for %s: %s", item.get("title", "")[:100], exc, exc_info=True)
            print(f"[ERROR] Telegram send failed for {item.get('title','')[:100]}: {exc}", flush=True)
    print(f"[Publication Lazy Refill] initial={initial_selected_count} lazy_replacements={lazy_replacements} final_attempt_queue={len(publication_queue)}", flush=True)
    if people_bootstrap_mode:
        status = "complete" if people_sent == 30 and len(people_candidates) == 30 else "in_progress"
        PEOPLE_BOOTSTRAP_RESULT = build_bootstrap_state(
            bootstrap_at=people_bootstrap_at,
            candidates=people_candidates,
            delivered_people=delivered_people,
            status=status,
            previous_state=people_state,
        )
        if PEOPLE_BOOTSTRAP_RESULT["people_count"] == 30 and PEOPLE_BOOTSTRAP_RESULT["delivered_count"] == 30:
            PEOPLE_BOOTSTRAP_RESULT["status"] = "complete"
            status = "complete"
        print(f"[People Bootstrap] status={status} delivered={PEOPLE_BOOTSTRAP_RESULT['delivered_count']}/30 baseline={PEOPLE_BOOTSTRAP_RESULT['people_count']}/30 bootstrap_at={people_bootstrap_at}", flush=True)
    else:
        PEOPLE_BOOTSTRAP_RESULT = None
    save_seen(seen_hashes, seen_signatures, source_history)
    print(f"Posts sent: {sent}/{len(publication_queue)}")


if __name__ == "__main__":
    try:
        main()
    except StateCorruptionError as exc:
        logger.error("[STATE] %s", exc, exc_info=True)
        raise SystemExit(1) from exc
