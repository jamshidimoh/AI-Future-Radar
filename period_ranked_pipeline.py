"""Production adapter: bounded global period ranking.

The module owns the final ranking calculation while delegating normal portfolio
construction to the unified editorial selection contract. Policy classifications
(Tier-0/protected), model-release detection, and person detection remain
independent metadata; they do not receive additive score bonuses here.
"""
from __future__ import annotations

import difflib
import logging
import time

import main as _pipeline
from src.model_release_priority import model_release_bonus
from src.priority_people import priority_people_features
from src.protected_story_identity import probable_same_story
from src.publication_guard import _canonical_url, _load_records, _normalized_title, _semantic_conflict
from src.semantic_dedup import get_story_signature
from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio

logger = logging.getLogger(__name__)

REGULAR_SAME_STORY_THRESHOLD = 0.82
EDITORIAL_WEIGHT = 0.75
SIGNAL_WEIGHT = 0.25
_PROTECTED_ACTIVITY_TERMS = (
    "announce", "announced", "announces", "launch", "launched", "launching",
    "release", "released", "releases", "unveil", "unveiled", "introduce", "introduced",
    "acquire", "acquired", "acquisition", "investment", "invested", "funding",
    "partnership", "appoint", "appointed", "raises", "raised", "founded", "initiative",
    "research project", "product", "model", "platform",
)
_PROTECTED_TECH_TERMS = (
    "artificial intelligence", " ai ", "machine learning", "deep learning", "llm", "agi",
    "openai", "anthropic", "deepmind", "nvidia", "meta ai", "google ai", "microsoft ai",
    "xai", "gpt", "claude", "gemini", "qwen", "llama", "reasoning model", "foundation model",
    "frontier model", "ai agent", "agentic ai", "robotics", "humanoid", "physical ai",
    "ai safety", "ai security", "ai governance", "ai policy", "ai regulation", "ai chip",
    "gpu", "npu", "tpu", "quantum computing", "quantum ai", "bci", "neurotechnology",
    "هوش مصنوعی", "یادگیری ماشین", "مدل زبانی", "رباتیک", "کوانتوم",
)


def _base_editorial_score(item):
    for key in ("radar_composite_score", "editorial_score_pre_signal", "final_editorial_score", "editorial_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
            if value:
                return value
        except (TypeError, ValueError):
            continue
    return 0.0


def canonical_rank_score(item):
    editorial = _base_editorial_score(item)
    signal = float(item.get("signal_score", 0) or 0)
    return round(editorial * EDITORIAL_WEIGHT + signal * SIGNAL_WEIGHT, 2)


def _base_score(item):
    return canonical_rank_score(item)


def _is_protected_publication_story(item):
    return bool(item.get("protected_slot"))


def _prepare_rank_features(items):
    for item in items:
        model_bonus = model_release_bonus(item)
        people, _person_tier0, people_bonus = priority_people_features(item)
        protected = _is_protected_publication_story(item)
        leader = str(item.get("leader") or item.get("watch_person") or "").strip()
        if protected and leader and leader not in people:
            people = list(people or []) + [leader]
        item["model_release_priority"] = bool(model_bonus)
        item["model_release_bonus_legacy"] = model_bonus
        item["priority_person_interview"] = bool(protected)
        item["priority_person_bonus_legacy"] = people_bonus if protected else 0.0
        item["priority_story_people"] = people
        item["_rank_is_tier0"] = protected
        item["final_editorial_score"] = canonical_rank_score(item)
    return items


def _score(item):
    return float(item.get("final_editorial_score", 0) or 0)


def _source_key(item):
    return str(item.get("source") or item.get("source_name") or "unknown").strip().lower() or "unknown"


def _rotation_source_counts(history, rotation_days):
    cutoff = time.time() - max(0, int(rotation_days)) * 86400
    counts = {}
    for record in history or []:
        if str(record.get("content_type") or "").strip().lower() == "education":
            continue
        try:
            ts = float(record.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            continue
        source = str(record.get("source") or "unknown").strip().lower() or "unknown"
        counts[source] = counts.get(source, 0) + 1
    return counts


def _diversify_normal_candidates(normal, max_posts, max_per_source, max_per_type, policy):
    policy = policy or {}
    rotation_days = int(policy.get("rotation_days", 7) or 7)
    try:
        source_history = _pipeline.load_source_history()
    except Exception as exc:
        logger.warning("Source history unavailable: %s", exc, exc_info=True)
        source_history = []
    recent_source_counts = _rotation_source_counts(source_history, rotation_days)
    contract = load_editorial_contract()
    requested = max(0, int(max_posts or 0))
    buffer = max(0, int(contract.get("replacement_buffer", 0) or 0))
    limit = min(len(normal), max(requested + buffer, int(contract["candidate_window"] or 0)))
    strict_relevance = bool(policy.get("strict_relevance", False))
    selected = select_regular_portfolio(normal, max_posts=limit, max_per_source=max_per_source, max_per_type=max_per_type, recent_source_counts=recent_source_counts, contract=contract, mission_aware=bool(policy.get("mission_aware", False)), strict_relevance=strict_relevance)
    source_counts = {}
    for item in selected:
        key = _source_key(item)
        source_counts[key] = source_counts.get(key, 0) + 1
    print(f"[Source Diversity Gate] rotation_days={rotation_days} candidates={len(normal)} selected={len(selected)} source_counts={source_counts} recent_source_counts={recent_source_counts} adaptive=true preferred_source_cap={contract['preferred_max_same_source']} hard_source_cap={contract['hard_max_same_source']} candidate_window={limit} replacement_buffer={buffer} mission_aware={bool(policy.get('mission_aware', False))} strict_relevance={strict_relevance}", flush=True)
    return selected


def _semantic_comparison_possible(candidate_title, candidate_summary, record):
    """Cheap necessary-condition filter before the expensive semantic guard.

    This function can only reject a comparison from further work; it never
    declares a duplicate. The full publication guard remains authoritative.
    """
    candidate_signature = get_story_signature({"title": candidate_title, "summary": candidate_summary})
    stored_signature = get_story_signature(record)
    shared_anchors = len(set(candidate_signature.get("anchors", [])) & set(stored_signature.get("anchors", [])))
    if shared_anchors >= 2:
        return True
    candidate_title_text = str(candidate_signature.get("title_text") or "")
    stored_title_text = str(stored_signature.get("title_text") or "")
    if not candidate_title_text or not stored_title_text:
        return False
    return difflib.SequenceMatcher(None, candidate_title_text, stored_title_text).ratio() >= 0.75


def _exclude_published_candidates(items):
    records = _load_records()
    if not records or not items:
        return items
    kept, blocked = [], {"canonical_url": 0, "title": 0, "semantic": 0}
    semantic_bypassed = protected_same_story_blocked = 0
    semantic_prefiltered = 0
    for item in items:
        candidate_url = _canonical_url(item.get("canonical_url") or item.get("link") or item.get("url") or "")
        title = _normalized_title(item.get("title") or "")
        summary = str(item.get("summary") or item.get("description") or "")
        protected = _is_protected_publication_story(item)
        conflict = conflict_record = None
        for record in records:
            record_url = _canonical_url(record.get("link", ""))
            if candidate_url and record_url and candidate_url == record_url:
                conflict, conflict_record = "canonical_url", record
                break
            stored_title = _normalized_title(record.get("title", ""))
            if title and stored_title and title == stored_title:
                conflict, conflict_record = "title", record
                break
        if conflict is None:
            if protected:
                for record in records:
                    if not str(record.get("title") or "").strip():
                        continue
                    if probable_same_story(item, record):
                        conflict, conflict_record = "semantic", record
                        protected_same_story_blocked += 1
                        break
                if conflict is None:
                    semantic_bypassed += 1
            else:
                for record in records:
                    if not str(record.get("title") or "").strip():
                        continue
                    if not _semantic_comparison_possible(title, summary, record):
                        semantic_prefiltered += 1
                        continue
                    if _semantic_conflict(title, summary, record) >= REGULAR_SAME_STORY_THRESHOLD:
                        conflict, conflict_record = "semantic", record
                        break
        if conflict:
            blocked[conflict] += 1
            if conflict == "semantic":
                print(f"[Pre-Ranking Publication Guard] semantic block title={str(item.get('title',''))[:90]} matched={str((conflict_record or {}).get('title',''))[:90]}", flush=True)
            continue
        kept.append(item)
    total_blocked = sum(blocked.values())
    if total_blocked or semantic_bypassed or protected_same_story_blocked or semantic_prefiltered:
        print(f"[Pre-Ranking Publication Guard] excluded={total_blocked} canonical={blocked['canonical_url']} title={blocked['title']} semantic={blocked['semantic']} semantic_prefiltered={semantic_prefiltered} protected_semantic_bypassed={semantic_bypassed} protected_same_story_blocked={protected_same_story_blocked} regular_semantic_threshold={REGULAR_SAME_STORY_THRESHOLD:.2f} remaining={len(kept)}", flush=True)
    return kept


def _priority_story_diversified(items):
    best_by_person = {}
    for item in items:
        people = list(item.get("priority_story_people") or [])
        if not people:
            leader = str(item.get("leader") or item.get("watch_person") or "").strip()
            people = [leader] if leader else [f"__item__{id(item)}"]
        for person in people:
            candidate_key = (_score(item), float(item.get("signal_score", 0) or 0), int(item.get("leader_source_authority", 0) or 0), str(item.get("published", "")))
            current = best_by_person.get(person)
            if current is None or candidate_key > current[0]:
                best_by_person[person] = (candidate_key, item)
    selected = {id(item): item for _, (_, item) in best_by_person.items()}
    return sorted(selected.values(), key=lambda x: (_score(x), float(x.get("signal_score", 0) or 0), int(x.get("leader_source_authority", 0) or 0), str(x.get("published", ""))), reverse=True)


def _global_ranked_selection(items, max_posts, max_per_source, max_per_type, policy):
    started = time.monotonic()
    eligible = [x for x in items if not x.get("duplicate") and not x.get("publication_blocked")]
    eligible = _exclude_published_candidates(eligible)
    _prepare_rank_features(eligible)

    # Leader-watch activity is protected for monitoring, but a weak activity
    # item must not consume one of the scarce protected publication slots.
    # Interviews and critical AI incidents retain their independent protection.
    try:
        protected_floor = float(getattr(_pipeline, "PROTECTED_SUMMARY_SCORE_FLOOR", 55.0) or 55.0)
    except (TypeError, ValueError):
        protected_floor = 55.0
    demoted_activity = 0
    for item in eligible:
        if not item.get("_rank_is_tier0"):
            continue
        if item.get("critical_ai_incident"):
            continue
        try:
            is_activity = bool(_pipeline._is_protected_leader_activity(item))
            is_interview = bool(_pipeline._is_protected_leader_interview(item))
        except Exception:
            is_activity = is_interview = False
        if not is_activity or is_interview:
            continue
        if _score(item) >= protected_floor:
            continue
        item["_rank_is_tier0"] = False
        item["priority_person_interview"] = False
        item["protected_slot"] = False
        item["protected_content"] = False
        demoted_activity += 1
        print(
            f"[Leader Protection Gate] demoted weak activity before ranking: {str(item.get('title', ''))[:120]} score={_score(item):.2f} floor={protected_floor:.2f}",
            flush=True,
        )
    if demoted_activity:
        print(f"[Leader Protection Gate] weak_activity_demoted={demoted_activity} protected_floor={protected_floor:.2f}", flush=True)

    print(f"[Ranking Timing] feature_cache items={len(eligible)} elapsed={time.monotonic()-started:.3f}s", flush=True)
    eligible.sort(key=lambda x: (int(bool(x.get("_rank_is_tier0"))), _score(x), int(bool(x.get("model_release_priority"))), float(x.get("signal_score", 0) or 0), int(x.get("leader_source_authority", 0) or 0), str(x.get("published", ""))), reverse=True)
    priority_candidates = [x for x in eligible if x.get("_rank_is_tier0")]
    normal = [x for x in eligible if not x.get("_rank_is_tier0")]
    priority = _priority_story_diversified(priority_candidates)
    priority_ids = {id(x) for x in priority}
    normal = [x for x in normal if id(x) not in priority_ids]
    contract = load_editorial_contract()
    candidate_window = max(4, min(len(normal), int(contract["candidate_window"] or 6) + int(contract.get("replacement_buffer", 0) or 0)))
    normal_window = _diversify_normal_candidates(normal, candidate_window, max_per_source, max_per_type, policy)
    ranked = priority + normal_window
    normal_rank = tier0_rank = 0
    for global_rank, item in enumerate(ranked, 1):
        is_tier0 = bool(item.get("_rank_is_tier0"))
        item["period_rank"] = global_rank
        item["publication_rank_assigned"] = True
        if is_tier0:
            tier0_rank += 1
            item["tier0_rank"] = tier0_rank
            item["normal_period_rank"] = None
        else:
            normal_rank += 1
            item["normal_period_rank"] = normal_rank
            item["tier0_rank"] = None
    print("[Global Final Ranking] " + ", ".join(f"rank={x['period_rank']} normal_rank={x.get('normal_period_rank')} tier0_rank={x.get('tier0_rank')} score={x['final_editorial_score']} priority_person={x.get('priority_person_interview',False)} model_release={x.get('model_release_priority',False)} title={str(x.get('title',''))[:90]}" for x in ranked), flush=True)
    print(f"[Tier0 Interview Priority] retained={len(priority)} quota_exempt=true unique_people=true", flush=True)
    print(f"[Normal Ranking Window] retained={len(normal_window)} normal_candidate_window={candidate_window} replacement_buffer={contract.get('replacement_buffer',0)} publication_capacity={contract['max_posts']}", flush=True)
    print(f"[Ranking Timing] total elapsed={time.monotonic()-started:.3f}s", flush=True)
    return ranked


def _eligibility_split(items, max_protected=2):
    """Compatibility entry point for legacy tests; ownership stays in main.py."""
    return _pipeline._split_protected(items, max_protected=max_protected)
