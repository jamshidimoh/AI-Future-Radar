"""Production adapter: bounded global period ranking.

The module owns the single final ranking calculation. Policy classifications
(Tier-0/protected), model-release detection, and person detection remain
independent metadata; they no longer receive additive score bonuses here.
"""
from __future__ import annotations

import time

import main as _pipeline
from model_release_priority import model_release_bonus
from publication_guard import _canonical_url, _load_records, _normalized_title, _semantic_conflict
from protected_story_identity import probable_same_story
from src.priority_people import priority_people_features

REGULAR_SAME_STORY_THRESHOLD = 0.82
EDITORIAL_WEIGHT = 0.75
SIGNAL_WEIGHT = 0.25


def _base_editorial_score(item):
    """Return the canonical editorial score before legacy signal mutation."""
    for key in ("editorial_score_pre_signal", "final_editorial_score", "editorial_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
            if value:
                return value
        except (TypeError, ValueError):
            continue
    return 0.0


def canonical_rank_score(item):
    """Combine independent editorial and technology signals exactly once.

    Editorial score remains the primary judgement layer. Signal score is an
    independent technical/evidence signal. Policy bonuses are intentionally
    excluded; policy controls routing/eligibility rather than value inflation.
    """
    editorial = _base_editorial_score(item)
    signal = float(item.get("signal_score", 0) or 0)
    return round(editorial * EDITORIAL_WEIGHT + signal * SIGNAL_WEIGHT, 2)


def _base_score(item):
    return canonical_rank_score(item)


def _is_priority_interview(item):
    try:
        return bool(priority_people_features(item)[1])
    except Exception:
        return False


def _is_protected_publication_story(item):
    return bool(item.get("protected_content") or item.get("_named_leader_interview") or _is_priority_interview(item))


def _prepare_rank_features(items):
    for item in items:
        model_bonus = model_release_bonus(item)
        people, is_tier0, people_bonus = priority_people_features(item)
        protected = _is_protected_publication_story(item)
        leader = str(item.get("leader") or item.get("watch_person") or "").strip()
        if protected and leader and leader not in people:
            people = list(people or []) + [leader]
        item["model_release_priority"] = bool(model_bonus)
        item["model_release_bonus_legacy"] = model_bonus
        item["priority_person_interview"] = bool(is_tier0 or protected)
        item["priority_person_bonus_legacy"] = people_bonus
        item["priority_story_people"] = people
        item["_rank_is_tier0"] = bool(is_tier0 or protected)
        item["final_editorial_score"] = canonical_rank_score(item)
    return items


def _score(item):
    return float(item.get("final_editorial_score", 0) or 0)


def _source_key(item):
    return str(item.get("source") or item.get("source_name") or "unknown").strip().lower() or "unknown"


def _content_type_key(item):
    return str(item.get("content_type") or "unknown").strip().lower() or "unknown"


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
    except Exception:
        source_history = []
    recent_source_counts = _rotation_source_counts(source_history, rotation_days)
    source_cap = max(1, int(max_per_source or 1))
    type_cap = max(1, int(max_per_type or 1))
    limit = max(0, int(max_posts or 0))
    selected, selected_source_counts, selected_type_counts = [], {}, {}

    def can_take(item):
        source = _source_key(item)
        content_type = _content_type_key(item)
        return selected_source_counts.get(source, 0) < source_cap and selected_type_counts.get(content_type, 0) < type_cap

    fresh = [x for x in normal if recent_source_counts.get(_source_key(x), 0) == 0]
    recent = [x for x in normal if recent_source_counts.get(_source_key(x), 0) > 0]
    for pool in (fresh, recent):
        for item in pool:
            if not can_take(item):
                continue
            selected.append(item)
            source, content_type = _source_key(item), _content_type_key(item)
            selected_source_counts[source] = selected_source_counts.get(source, 0) + 1
            selected_type_counts[content_type] = selected_type_counts.get(content_type, 0) + 1
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break
    print(f"[Source Diversity Gate] rotation_days={rotation_days} fresh_candidates={len(fresh)} recent_candidates={len(recent)} selected={len(selected)} source_counts={selected_source_counts} recent_source_counts={recent_source_counts}", flush=True)
    return selected


def _exclude_published_candidates(items):
    records = _load_records()
    if not records or not items:
        return items
    kept, blocked = [], {"canonical_url": 0, "title": 0, "semantic": 0}
    semantic_bypassed = protected_same_story_blocked = 0
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
    if total_blocked or semantic_bypassed or protected_same_story_blocked:
        print(f"[Pre-Ranking Publication Guard] excluded={total_blocked} canonical={blocked['canonical_url']} title={blocked['title']} semantic={blocked['semantic']} protected_semantic_bypassed={semantic_bypassed} protected_same_story_blocked={protected_same_story_blocked} regular_semantic_threshold={REGULAR_SAME_STORY_THRESHOLD:.2f} remaining={len(kept)}", flush=True)
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
    print(f"[Ranking Timing] feature_cache items={len(eligible)} elapsed={time.monotonic()-started:.3f}s", flush=True)
    eligible.sort(key=lambda x: (int(bool(x.get("_rank_is_tier0"))), _score(x), int(bool(x.get("model_release_priority"))), float(x.get("signal_score", 0) or 0), int(x.get("leader_source_authority", 0) or 0), str(x.get("published", ""))), reverse=True)
    priority_candidates = [x for x in eligible if x.get("_rank_is_tier0")]
    normal = [x for x in eligible if not x.get("_rank_is_tier0")]
    priority = _priority_story_diversified(priority_candidates)
    priority_ids = {id(x) for x in priority}
    normal = [x for x in normal if id(x) not in priority_ids]
    normal_window = _diversify_normal_candidates(normal, max(4, min(len(normal), max_posts)), max_per_source, max_per_type, policy)
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
    print(f"[Normal Ranking Window] retained={len(normal_window)} normal_rank=1..{len(normal_window)}", flush=True)
    print(f"[Ranking Timing] total elapsed={time.monotonic()-started:.3f}s", flush=True)
    return ranked


def _eligibility_split(items, max_protected=2):
    candidates, regular = [], []
    for raw in items:
        item = dict(raw)
        if _pipeline._is_protected_leader_interview(item) or _pipeline._is_protected_leader_activity(item):
            item["protected_content"] = True
            item["protected_reason"] = "leader_interview_or_activity"
            item["_ai_link"] = True
            item["leader_watch_protected"] = True
            item["leader_source_authority"] = _pipeline._leader_source_authority(item)
            leader = str(item.get("leader") or item.get("watch_person") or "").strip()
            if leader:
                item["priority_story_people"] = [leader]
            item["_rank_is_tier0"] = True
            candidates.append(item)
        else:
            regular.append(item)
    candidates.sort(key=lambda x: (int(x.get("leader_priority", 0) or 0), int(x.get("leader_source_authority", 0) or 0), 1 if _pipeline._direct_interview_signal(x) else 0, 0 if str(x.get("content_type") or "").lower() == "product_news" else 1, float(x.get("editorial_score", 0) or 0), str(x.get("published", ""))), reverse=True)
    limit = max(0, int(max_protected))
    selected = candidates[:limit]
    regular.extend(candidates[limit:])
    print(f"[Protected Leader Eligibility] candidates={len(candidates)} slots_reserved={len(selected)}", flush=True)
    return selected, regular


def main(hooks=None):
    merged = dict(hooks or {})
    merged.setdefault("select_editorial", _global_ranked_selection)
    merged.setdefault("split_protected", _eligibility_split)
    return _pipeline.main(hooks=merged)

select_editorial = _global_ranked_selection

for _name in ("load_yaml", "LEADER_CONFIG_PATH", "_direct_interview_signal", "summarize_item", "format_post", "mark_as_seen", "send_to_telegram_safe", "resolve_source_image", "_source_tier", "_persist_item_success"):
    if hasattr(_pipeline, _name):
        globals()[_name] = getattr(_pipeline, _name)
