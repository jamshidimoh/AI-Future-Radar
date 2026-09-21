"""Independent Voices / Perspectives editorial lane.

Purpose: surface substantive interviews, talks, expert views, debates, high-value
quotes, and material news explicitly attributed to watched experts. This lane is
independent from Normal News, Technical Trend and Mind/Science/Future.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from src.expert_registry import apply_expert_features
from src.priority_people import matched_priority_people

MAX_VOICES_PER_PERIOD = 1
VOICES_RANK_WINDOW = 12

VOICE_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a", "debate", "opinion", "essay", "commentary"}
VOICE_SIGNALS = (r"\binterview\b", r"\bpodcast\b", r"\bconversation\b", r"\bfireside\b", r"\bq&a\b", r"\bdiscussion\b", r"\bdebate\b", r"\btalk\b", r"\blecture\b", r"\bkeynote\b", r"\bexpert view\b", r"\bopinion\b", r"\bcommentary\b", r"\bquote\b", r"\bsays\b", r"\bargues\b", r"مصاحبه", r"گفتگو", r"گفت‌وگو", r"سخنرانی", r"دیدگاه", r"نظر", r"نقل قول")
PERSON_KEYS = ("watch_person", "person", "person_name", "leader", "leader_name", "expert", "expert_name", "author", "speaker", "guest", "interviewee", "researcher")
MISSION_AREAS = {"ai", "ai_core", "convergence", "mind", "mind_cognition", "future", "future_governance"}
EXCLUDED_SOURCE_MARKERS = ("reddit", "community", "aggregator", "arxiv.org", "arxiv")
AI_ANCHORS = ("artificial intelligence", "machine learning", "llm", "foundation model", "agent", "agentic", "reasoning", "robotics", "neuroscience", "consciousness", "bci", "quantum", "genomics", "synthetic biology", "هوش مصنوعی", "یادگیری ماشین")


def _text(item: dict[str, Any]) -> str:
    fields = ("title", "summary", "description", "mission_area", "category", "content_type", "tags", "keywords", "source", "source_name", "publisher", *PERSON_KEYS)
    return " ".join(str(item.get(k) or "") for k in fields).casefold()


def _source_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k) or "") for k in ("source", "source_name", "source_type", "source_domain", "publisher")).casefold()


def _has_voice_signal(item: dict[str, Any]) -> bool:
    text = _text(item)
    content_type = str(item.get("content_type") or "").strip().casefold()
    source_type = str(item.get("source_type") or item.get("type") or item.get("format") or "").strip().casefold()
    return content_type in VOICE_TYPES or source_type in VOICE_TYPES or any(re.search(p, text) for p in VOICE_SIGNALS)


def _matched_people(item: dict[str, Any]) -> list[str]:
    try: return list(matched_priority_people(item, text=_text(item)))
    except Exception: return []


def _expert_identity(item: dict[str, Any]) -> tuple[list[str], bool, float]:
    try:
        apply_expert_features(item)
    except Exception:
        return [], False, 0.0
    people = [str(x).strip() for x in (item.get("people") or []) if str(x).strip()]
    content_type = str(item.get("content_type") or "").strip().casefold()
    source_tier = int(item.get("source_tier", 3) or 3)
    registered_voice = bool(
        people
        and content_type in VOICE_TYPES
        and source_tier <= 2
    )
    return people, bool(item.get("expert_deep_lane")) or registered_voice, float(item.get("expert_score", 0.0) or 0.0)


def _has_person_signal(item: dict[str, Any]) -> bool:
    expert_people, expert_deep_lane, _ = _expert_identity(item)
    if expert_people or expert_deep_lane:
        return True
    return bool(
        _matched_people(item)
        or any(str(item.get(k) or "").strip() for k in PERSON_KEYS)
    )


def _priority_person_signal(item: dict[str, Any]) -> bool:
    expert_people, expert_deep_lane, _ = _expert_identity(item)
    return bool(
        expert_people
        or expert_deep_lane
        or _matched_people(item)
        or item.get("is_leader_watch")
        or item.get("leader_watch_protected")
        or item.get("priority_person_signal")
    )


def _ai_relevant(item: dict[str, Any]) -> bool:
    mission = str(item.get("mission_area") or item.get("category") or "").strip().casefold()
    if mission in {"ai", "ai_core"}:
        return True
    text = _text(item)
    return any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", text) for a in AI_ANCHORS)


def _voice_source_excluded(item: dict[str, Any]) -> bool:
    # Google News is a discovery transport, not the editorial source itself.
    # For leader-watch items, inspect the actual publisher fields and ignore
    # "news_aggregator" transport metadata unless the publisher is itself excluded.
    actual_source_text = " ".join(
        str(item.get(k) or "") for k in ("source", "source_name", "source_domain", "publisher")
    ).casefold()
    if any(marker in actual_source_text for marker in EXCLUDED_SOURCE_MARKERS):
        return True
    transport_text = " ".join(
        str(item.get(k) or "") for k in ("source_type",)
    ).casefold()
    is_leader_watch = bool(item.get("is_leader_watch") or item.get("leader_watch_protected"))
    return (not is_leader_watch) and any(marker in transport_text for marker in EXCLUDED_SOURCE_MARKERS)


def is_voices_candidate(item: dict[str, Any]):
    if item.get("duplicate") or item.get("publication_blocked") or item.get("_publication_blocked"): return False
    if item.get("protected_slot") and not item.get("_rank_is_tier0"): return False
    if item.get("technical_trend_lane_selected") or item.get("mind_lane_selected"): return False
    if str(item.get("content_type") or "").strip().casefold() == "education": return False
    if _voice_source_excluded(item): return False
    mission = str(item.get("mission_area") or item.get("category") or "").strip().casefold()
    if mission not in MISSION_AREAS: return False
    expert_people, expert_deep_lane, _ = _expert_identity(item)
    voice_signal = _has_voice_signal(item)
    person_signal = _has_person_signal(item)
    priority_person = _priority_person_signal(item)
    substantive_identity = bool(
        expert_people or expert_deep_lane or _matched_people(item)
        or any(str(item.get(k) or "").strip() for k in PERSON_KEYS)
    )
    return _ai_relevant(item) and person_signal and substantive_identity and (
        voice_signal or priority_person or expert_deep_lane
    )


def _recency_bonus(item: dict[str, Any]) -> float:
    raw = str(item.get("published") or item.get("published_at") or item.get("date") or "").strip()
    if not raw: return 0.0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00")); dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc); age = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    except ValueError: return 0.0
    return 10.0 if age <= 3 else 7.0 if age <= 7 else 4.0 if age <= 14 else 2.0 if age <= 30 else 0.0


def voices_perspectives_score(item: dict[str, Any]) -> float:
    score = 0.0
    voice_signal = _has_voice_signal(item)
    priority_person = _priority_person_signal(item)
    expert_people, expert_deep_lane, expert_score = _expert_identity(item)
    if voice_signal: score += 24.0
    if _has_person_signal(item): score += 18.0
    if priority_person: score += 12.0
    if expert_people: score += 8.0
    if expert_deep_lane: score += 12.0
    # Numeric person priority and registry priors must not make one watched expert
    # outrank another. Identity/deep-lane signals remain eligibility/quality signals,
    # while recency decides between otherwise comparable voices.
    try: tier = int(item.get("source_tier", 3) or 3)
    except (TypeError, ValueError): tier = 3
    score += {1: 16.0, 2: 10.0, 3: 3.0}.get(tier, 0.0)
    if str(item.get("source_type") or "").casefold() in {"official", "university", "scientific", "specialist"}: score += 8.0
    text = _text(item)
    if any(re.search(p, text) for p in (r"why it matters", r"implication", r"future", r"reasoning", r"consciousness", r"آینده", r"پیامد")): score += 8.0
    score += _recency_bonus(item)
    return round(min(100.0, score), 2)


def _publication_guard_conflict(item: dict[str, Any], *, title_only: bool = False) -> tuple[bool, str]:
    """Use the final publication guard as a conservative pre-selection gate.

    The second title-only pass closes the gap where an item has little or no
    source summary at selection time but the later LLM-rendered summary makes it
    collide with an already published story. This only rejects candidates; it
    never weakens the final semantic duplicate guard.
    """
    try:
        from src.publication_guard import check_before_publish
        title = str(item.get("title") or "").strip()
        if not title: return False, ""
        summary = "" if title_only else str(item.get("summary") or item.get("description") or "").strip()
        why = "" if title_only else str(item.get("why_it_matters") or "").strip()
        text = "\n".join([title, f"خلاصه: {summary}", f"چرا مهم است: {why}"])
        return check_before_publish(text, str(item.get("link") or item.get("url") or ""))
    except Exception:
        return True, "preselection_guard_unavailable"


def _already_published_conflict(item: dict[str, Any]) -> bool:
    allowed, reason = _publication_guard_conflict(item, title_only=False)
    if not allowed:
        item["voices_publication_conflict"] = reason
        return True
    # If the source summary is missing, or the first pass had no substantive
    # context, run a stricter title-only history comparison before consuming the
    # single Voices slot. A false negative here is preferable to selecting a
    # candidate whose later generated summary becomes a duplicate.
    summary = str(item.get("summary") or item.get("description") or "").strip()
    if not summary:
        allowed, reason = _publication_guard_conflict(item, title_only=True)
        if not allowed:
            item["voices_publication_conflict"] = reason
            return True
    return False


def choose_voices_candidate(candidates: Iterable[dict[str, Any]], *, existing_ids: set[int] | None = None, max_items: int = MAX_VOICES_PER_PERIOD) -> list[dict[str, Any]]:
    existing_ids = existing_ids or set(); eligible = []
    for item in candidates or []:
        if id(item) in existing_ids or not is_voices_candidate(item): continue
        if _already_published_conflict(item): continue
        item["voices_perspectives_score"] = voices_perspectives_score(item)
        expert_people, expert_deep_lane, expert_score = _expert_identity(item)
        item["voice_identity_people"] = expert_people
        item["voice_expert_deep_lane"] = expert_deep_lane
        item["voice_expert_score"] = expert_score
        eligible.append(item)
    eligible.sort(key=lambda x: (-float(x.get("voices_perspectives_score", 0) or 0), str(x.get("published") or "")))
    selected = eligible[:max(0, int(max_items))]
    for rank, item in enumerate(selected, 1):
        item["voices_perspectives_lane_selected"] = True; item["editorial_lane"] = "voices_perspectives"; item["voices_period_rank"] = rank; item["normal_period_rank"] = None; item["mind_period_rank"] = None; item["technical_trend_period_rank"] = None; item["voices_lane_independent"] = True; item["voices_lane_reason"] = "top_independent_voices_perspectives_score"
    return selected
