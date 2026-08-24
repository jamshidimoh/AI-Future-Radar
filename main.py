import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from content_selector import select_content as _select_content
from dedup import filter_new_items, load_seen, load_source_history, mark_as_seen, save_seen
from editorial import enrich_items, filter_ai_relevance, filter_low_signal, select_editorial
from fetch_google_news import fetch_google_news_items
from fetch_rss import fetch_rss_items
from fetch_youtube import fetch_youtube_items
from interview_evidence import has_interview_evidence
from mission_selector import _source_tier
from send_telegram import format_post, resolve_source_image, send_to_telegram_safe
from signal_engine import enrich_signal_items
from summarize import summarize_item
from semantic_dedup import deduplicate_semantically
from story_gate import gate_story_candidates
from publication_contract import unique_candidates

CONFIG_PATH = ROOT / "config" / "sources.yaml"
LEADER_CONFIG_PATH = ROOT / "config" / "leader_watchlist.yaml"
SELECTION_POLICY_PATH = ROOT / "config" / "selection_policy.yaml"


def load_yaml(path):
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _text(item):
    return " ".join(str(item.get(k) or "") for k in ("title", "summary", "description")).lower()


def _contains_person(text, name):
    return str(name or "").strip().lower() in str(text or "").lower()


def _has_explicit_interview_evidence(item):
    return has_interview_evidence(item)


def _direct_interview_signal(item):
    return has_interview_evidence(item)


def _leader_activity_signal(item):
    ctype = str(item.get("content_type") or "").lower().strip(); text = _text(item)
    activity_terms = ("launch", "launched", "release", "released", "unveil", "introduced", "product", "model", "platform", "startup", "company", "fund", "investment", "acquisition", "partnership", "appoint", "appointed", "research project", "initiative", "new course", "course", "paper", "project", "announcement", "funding", "raises", "raised", "joins", "founded", "founder", "ceo")
    return ctype in {"product_news", "official"} or bool(item.get("leader_activity_signal")) or any(term in text for term in activity_terms)


def _leader_people(leader_config):
    names, priorities = [], {}
    for group in (leader_config.get("people") or {}).values():
        for person in (group.get("names") or []):
            name = str(person).strip()
            if name:
                names.append(name); priorities[name] = int(group.get("priority", 0) or 0)
    return sorted(set(names)), priorities


def _merge_unique_dicts(*lists, key):
    out, seen = [], set()
    for seq in lists:
        for item in seq or []:
            value = str(item.get(key) or "")
            if value not in seen:
                seen.add(value); out.append(item)
    return out


def _mark_leader_items(items):
    for item in items:
        item["is_leader"] = True; item["is_leader_watch"] = True
    return items


def _annotate_named_leader_interviews(items, leader_people, leader_priorities=None):
    names = sorted({str(x).strip() for x in (leader_people or []) if str(x).strip()}, key=len, reverse=True)
    priorities = {str(k).strip(): int(v or 0) for k, v in (leader_priorities or {}).items()}
    matched = protected = watch_candidates = 0
    for item in items:
        existing = str(item.get("leader") or item.get("watch_person") or "").strip()
        if existing:
            if existing in names:
                watch_candidates += 1; item["leader_priority"] = priorities.get(existing, int(item.get("leader_priority", 0) or 0))
                if _direct_interview_signal(item):
                    item["_named_leader_interview"] = True; item["is_leader_watch"] = True; item["leader_watch_protected"] = True; matched += 1
                elif _leader_activity_signal(item):
                    item["leader_activity_signal"] = True; item["is_leader_watch"] = True; item["leader_watch_protected"] = True; protected += 1
            continue
        text = _text(item)
        for name in names:
            if _contains_person(text, name):
                item["watch_person"] = name; item["leader"] = name; item["is_leader_watch"] = True; item["leader_priority"] = priorities.get(name, int(item.get("leader_priority", 0) or 0)); watch_candidates += 1
                if _direct_interview_signal(item):
                    item["_named_leader_interview"] = True; item["leader_watch_protected"] = True; matched += 1
                elif _leader_activity_signal(item):
                    item["leader_activity_signal"] = True; item["leader_watch_protected"] = True; protected += 1
                break
    print(f"[Leader Identity Recovery] verified_interviews={matched} | activity_protected={protected} | watchlist_candidates={watch_candidates}"); return items


def _is_protected_leader_interview(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if not leader:
        return False
    if not (item.get("is_leader_watch") or item.get("leader_watch_protected") or item.get("_named_leader_interview")):
        return False
    return has_interview_evidence(item)


def _is_protected_leader_activity(item):
    leader = str(item.get("leader") or item.get("watch_person") or "").strip(); return bool(leader and (item.get("is_leader_watch") or item.get("leader_watch_protected")) and _leader_activity_signal(item))


def _leader_source_authority(item):
    try: tier = int(_source_tier(item))
    except Exception: tier = 3
    return max(0, 4 - tier)


def _split_protected(items, max_protected=2):
    candidates, regular = [], []
    for raw in items:
        item = dict(raw)
        if _is_protected_leader_interview(item) or _is_protected_leader_activity(item):
            item["protected_content"] = True; item["protected_reason"] = "leader_interview_or_activity"; item["_ai_link"] = True; item["leader_watch_protected"] = True; item["leader_source_authority"] = _leader_source_authority(item); candidates.append(item)
        else:
            regular.append(item)
    candidates.sort(key=lambda x: (int(x.get("leader_priority", 0) or 0), int(x.get("leader_source_authority", _leader_source_authority(x)) or 0), 1 if _is_protected_leader_interview(x) else 0, 0 if str(x.get("content_type") or "").lower() == "product_news" else 1, float(x.get("editorial_score", 0) or 0), str(x.get("published", ""))), reverse=True)
    selected = candidates[:max(0, int(max_protected))]; regular.extend(candidates[len(selected):]); return selected, regular


def _apply_signal_ranking(items):
    for item in items:
        signal = float(item.get("signal_score", 0) or 0); editorial = float(item.get("editorial_score", 0) or 0); item["editorial_score_pre_signal"] = editorial; item["editorial_score"] = round(editorial + signal * 0.30, 2)
    return items


def _leader_protection_diagnostic(verified_before_filter, new_items):
    surviving = sum(_is_protected_leader_interview(x) or _is_protected_leader_activity(x) for x in new_items); seen_blocked = max(0, int(verified_before_filter) - int(surviving)); print(f"[Leader Protection Audit] verified={verified_before_filter} | new_after_seen={surviving} | blocked_as_seen={seen_blocked}"); return surviving, seen_blocked


def _persist_item_success(item, seen_hashes, seen_signatures, source_history):
    if str(item.get("content_type") or "").lower() == "education":
        education_id = item.get("education_id", "unknown"); identity = f"education:{education_id}"; item["publication_identity"] = identity; mark_as_seen(item, seen_hashes, seen_signatures, source_history); save_seen(seen_hashes, seen_signatures, source_history); print(f"[Publication Ledger] persisted education={identity}", flush=True); return
    mark_as_seen(item, seen_hashes, seen_signatures, source_history); save_seen(seen_hashes, seen_signatures, source_history); identity = str(item.get("canonical_url") or item.get("link") or item.get("url") or item.get("title") or "")[:120]; print(f"[Publication Ledger] persisted story={item.get('title','')[:100]} identity={identity}", flush=True)


def main(hooks=None):
    hooks = dict(hooks or {})
    select_editorial_fn = hooks.get("select_editorial", select_editorial)
    split_protected_fn = hooks.get("split_protected", _split_protected)
    summarize_fn = hooks.get("summarize_item", summarize_item)
    format_fn = hooks.get("format_post", format_post)
    resolve_image_fn = hooks.get("resolve_source_image", resolve_source_image)
    deliver_fn = hooks.get("send_to_telegram_safe", send_to_telegram_safe)
    persist_fn = hooks.get("persist_item_success", _persist_item_success)
    config = load_yaml(CONFIG_PATH); leader_config = load_yaml(LEADER_CONFIG_PATH); selection = load_yaml(SELECTION_POLICY_PATH).get("selection", {}); policy = load_yaml(SELECTION_POLICY_PATH).get("editorial", {}); categories = config["categories"]; max_posts = int(selection.get("max_posts", 4)); max_per_source = int(selection.get("max_items_per_source", 2)); max_per_type = int(selection.get("max_items_per_content_type", 2)); leader_protected_max = int(policy.get("leader_protected_max", 2)); bridge_keywords = config.get("ai_bridge_keywords", []); story_threshold = float(selection.get("story_similarity_threshold", 0.45)); leader_people, leader_priorities = _leader_people(leader_config)
    youtube_channels = _merge_unique_dicts(config.get("youtube_channels", []), leader_config.get("youtube_channels", []), key="name"); leader_channel_names = {x.get("name") for x in leader_config.get("youtube_channels", [])}; base_youtube_channels = [x for x in youtube_channels if x.get("name") not in leader_channel_names]; leader_youtube_channels = [x for x in youtube_channels if x.get("name") in leader_channel_names]; base_queries = list(config.get("google_news_queries", [])); leader_queries = list(leader_config.get("google_news_queries", []))
    print("[1/7] Discovery: RSS / university / scientific / specialist sources"); rss_items = fetch_rss_items(config["rss_sources"], categories); print(f"RSS items: {len(rss_items)}")
    print("[2/7] Discovery: YouTube / interviews / podcasts / lectures"); base_youtube = fetch_youtube_items(base_youtube_channels, max_age_hours=72, ai_bridge_keywords=bridge_keywords); leader_youtube = _mark_leader_items(fetch_youtube_items(leader_youtube_channels, max_age_hours=720, ai_bridge_keywords=bridge_keywords)); youtube_items = base_youtube + leader_youtube; print(f"YouTube items: {len(youtube_items)} | leader-channel items: {len(leader_youtube)}")
    print("[3/7] Discovery: Google News + Leader Watchlist"); base_news = fetch_google_news_items(base_queries, max_age_hours=36, max_workers=4); leader_news = _mark_leader_items(fetch_google_news_items(leader_queries, max_age_hours=720, max_workers=1, inter_query_delay=0.35)); news_items = base_news + leader_news; print(f"Google News items: {len(news_items)} | leader candidates: {len(leader_news)}")
    all_items = rss_items + youtube_items + news_items; print(f"Raw total: {len(all_items)}"); all_items = _annotate_named_leader_interviews(all_items, leader_people, leader_priorities); verified_leader_interviews = sum(_is_protected_leader_interview(x) or _is_protected_leader_activity(x) for x in all_items); seen_hashes, seen_signatures = load_seen(); source_history = load_source_history(); new_items = filter_new_items(all_items, seen_hashes); print(f"After link dedup: {len(new_items)}"); _leader_protection_diagnostic(verified_leader_interviews, new_items)
    protected_items, regular_items = split_protected_fn(new_items, max_protected=leader_protected_max); print(f"[Protected Leader Watch] selected={len(protected_items)} max={leader_protected_max} | regular_pool={len(regular_items)}"); print("[4/7] AI-first relevance gate (regular pool only)"); regular_items = filter_ai_relevance(regular_items, bridge_keywords); print("[5/7] Story clustering and canonical-source selection"); regular_enriched = enrich_items(regular_items, leader_priorities, source_history, policy); regular_enriched = enrich_signal_items(regular_enriched); _apply_signal_ranking(regular_enriched); regular_enriched.sort(key=lambda x: (x.get("editorial_score", 0), x.get("signal_score", 0)), reverse=True); leader_pool = [x for x in regular_enriched if x.get("is_leader") or x.get("leader_signal")]; regular_pool = [x for x in regular_enriched if not (x.get("is_leader") or x.get("leader_signal"))]; leader_before, regular_before = len(leader_pool), len(regular_pool)
    editorial_pool = gate_story_candidates(protected_items, leader_pool, regular_pool, seen_signatures, threshold=story_threshold); editorial_pool = sorted(editorial_pool, key=lambda x: (x.get("editorial_score", 0), x.get("signal_score", 0)), reverse=True); leader_after = sum(1 for x in editorial_pool if x.get("is_leader") or x.get("leader_signal")); regular_after = sum(1 for x in editorial_pool if not (x.get("is_leader") or x.get("leader_signal"))); protected_after = sum(1 for x in editorial_pool if x.get("protected_content")); print(f"[Story Gate] leaders={leader_before}->{leader_after} | regular={regular_before}->{regular_after} | protected={protected_after} | final stories={len(editorial_pool)}")
    selected_regular = select_editorial_fn(editorial_pool, max_posts=max_posts, max_per_source=max_per_source, max_per_type=max_per_type, policy=policy); protected_candidates = [x for x in editorial_pool if x.get("protected_content")]; protected_selected = sorted(protected_candidates, key=lambda x: (int(x.get("leader_priority", 0) or 0), int(x.get("leader_source_authority", 0) or 0), 1 if _direct_interview_signal(x) else 0, x.get("published", "")), reverse=True)[:leader_protected_max]
    selected = unique_candidates(protected_selected + selected_regular)
    print(f"[Selection Guard] protected={len(protected_selected)} selected_unique={len(selected)} cap={leader_protected_max + max_posts}", flush=True)
    selected = filter_new_items(selected, seen_hashes)
    if not selected:
        print("[Final Publication Guard] no publishable items remain", flush=True); save_seen(seen_hashes, seen_signatures, source_history); print("Posts sent: 0/0"); return
    print("[6/7] AI processing / summarization")
    for item in selected:
        summary = summarize_fn(item)
        if summary: item.update(summary)
        else: item["_publication_blocked"] = True; print(f"[Editorial Gate] skipped candidate: {str(item.get('title',''))[:120]}", flush=True)
        item["source_image"] = resolve_image_fn(item)
    print("[7/7] Telegram publication"); sent = 0
    for item in selected:
        if item.get("_publication_blocked"): continue
        try:
            source_name = str(item.get("source") or item.get("source_name") or "منبع"); link = str(item.get("link") or item.get("url") or ""); post = format_fn(item, source_name, link, is_video=str(item.get("source_type") or "").lower() in {"youtube", "video"}, published=item.get("published", ""), content_type=item.get("content_type", "news"), source_tier=item.get("source_tier", 3), source_type=item.get("source_type", "news"), leader=item.get("leader") or item.get("watch_person") or ""); result = deliver_fn(post, image_url=str(item.get("source_image") or ""), source_link=link)
            if hasattr(result, "status"):
                status = getattr(result, "status")
                status_value = getattr(status, "value", str(status))
                if status_value == "delivered":
                    sent += 1; persist_fn(item, seen_hashes, seen_signatures, source_history); continue
                if status_value in {"policy_blocked", "rejected", "duplicate"}:
                    print(f"[Publication Contract] candidate rejected reason={getattr(result, 'reason', '')}; continuing to next ranked candidate", flush=True)
                    continue
                raise RuntimeError(f"Telegram transport failure: {getattr(result, 'reason', 'unknown')}" )
            if not result:
                raise RuntimeError("Telegram delivery returned false")
            sent += 1; persist_fn(item, seen_hashes, seen_signatures, source_history)
        except Exception as exc:
            print(f"[ERROR] Telegram send failed for {item.get('title','')[:100]}: {exc}", flush=True)
    save_seen(seen_hashes, seen_signatures, source_history); print(f"Posts sent: {sent}/{len(selected)}")

if __name__ == "__main__":
    main()
