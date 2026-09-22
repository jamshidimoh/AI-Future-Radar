"""Independent Mind/Ideas/Voices editorial lane.

This lane has its own relevance score and selection policy. It is deliberately
independent from the normal-news ranking floor: NORMAL_SCORE_FLOOR is never used
for eligibility or selection here. Shared publication-history, source-safety and
final editorial quality contracts remain enforced downstream.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from src.future_significance import build_future_features

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = ROOT / "config" / "pioneers.yaml"
SPECIAL_MAX_PER_PERIOD = 2
SPECIAL_RANK_WINDOW = 12
MIND_IDEAS_VOICES_SCORE_FLOOR = 50.0

INTERVIEW_TYPES = {
    "interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a",
}
INTERVIEW_SIGNAL_TERMS = (r"\binterview\b", r"\bpodcast\b", r"\bconversation\b", r"\bfireside\b", r"\bq&a\b", r"\bdiscussion\b", r"\bguest\b", r"\bepisode\b")
MISSION_AREAS = {"mind", "mind_cognition", "future", "future_governance", "convergence", "ai", "ai_core"}
SPECIAL_SIGNAL_PATTERNS = (
    r"\bconsciousness\b", r"\bartificial consciousness\b", r"\bmachine consciousness\b",
    r"\bself-awareness\b", r"\bsentience\b", r"\bqualia\b", r"\bcognitive science\b",
    r"\bphilosophy of mind\b", r"\bphilosophy of science\b", r"\bphilosophy of technology\b",
    r"\bphilosophy of ai\b", r"\bepistemology of ai\b", r"\bawareness\b", r"\bcognition\b",
    r"\bneuroscience\b", r"\bneurotechnology\b", r"\bbrain-computer interface\b", r"\bbrain-computer\b",
    r"\bgenomics\b", r"\bgenetic\b", r"\bgene editing\b", r"\bsynthetic biology\b",
    r"\bfuturology\b", r"\bfutures? research\b", r"\bforesight\b", r"\bfuture studies\b",
    r"\bsociology\b", r"\bsocial science\b", r"\banthropology\b", r"\bsociety and technology\b", r"\btechnology and society\b",
    r"\bai\s+and\s+(?:the\s+)?mind\b",
)
PERSON_KEYS = (
    "watch_person", "person", "person_name", "leader", "leader_name", "expert", "expert_name",
    "author", "speaker", "guest", "interviewee", "researcher",
)


def _text(item: dict[str, Any]) -> str:
    fields = ("title", "summary", "description", "mission_area", "category", "content_type", "tags", "keywords", *PERSON_KEYS)
    return " ".join(str(item.get(key) or "") for key in fields).casefold()


def _registry_names() -> set[str]:
    try:
        document = yaml.safe_load(PEOPLE_PATH.read_text(encoding="utf-8")) or {}
        return {
            str(person.get("name")).strip().casefold()
            for person in document.get("people", []) or []
            if isinstance(person, dict) and str(person.get("name") or "").strip()
        }
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return set()


def _named_registry_person(item: dict[str, Any]) -> bool:
    names = _registry_names()
    if not names:
        return False
    text = _text(item)
    values = [str(item.get(key) or "").strip().casefold() for key in PERSON_KEYS]
    return any(name in text or name == value for name in names for value in values)


def _explicit_person_signal(item: dict[str, Any]) -> bool:
    classification = item.get("leader_signal_classification") or {}
    if isinstance(classification, dict) and classification.get("accepted"):
        return True
    for key in ("is_leader_watch", "expert_signal", "expert_source_signal", "priority_person_signal"):
        if item.get(key):
            return True
    try:
        return int(item.get("leader_priority", 0) or 0) >= 8
    except (TypeError, ValueError):
        return False


def _trusted_source(item: dict[str, Any]) -> bool:
    source_text = " ".join(
        str(item.get(key) or "")
        for key in ("source", "source_name", "source_type", "source_domain", "publisher")
    ).casefold()
    return not any(marker in source_text for marker in ("reddit", "community", "aggregator"))


def _mission(item: dict[str, Any]) -> str:
    return str(item.get("mission_area") or item.get("category") or "").strip().casefold()


def _thematic_signal(item: dict[str, Any]) -> bool:
    return any(re.search(pattern, _text(item)) for pattern in SPECIAL_SIGNAL_PATTERNS)


def _ai_relevant(item: dict[str, Any]) -> bool:
    text = _text(item)
    mission = _mission(item)
    if mission in {"mind", "mind_cognition"}:
        return True
    ai_terms = (
        "artificial intelligence", "machine learning", "llm", "foundation model",
        "agentic", "reasoning", "frontier model", "ai safety", "ai governance",
        "robotics", "physical ai", "computer use", "neurotechnology", "bci",
        "genomics", "synthetic biology", "quantum computing", "هوش مصنوعی",
        "یادگیری ماشین", "مدل بنیادی", "عامل هوشمند", "ربات",
    )
    if any(term in text for term in ai_terms):
        return True
    return bool(re.search(r"\bai\b", text))


def _importance_evidence(item: dict[str, Any]) -> bool:
    """Require substantive importance, not merely topical or interview metadata."""
    classification = str(item.get("editorial_class") or "").strip().casefold()
    if classification in {"research_breakthrough", "leader_interview", "convergence_signal", "major_industry_news"}:
        return True

    source_tier = 3
    try:
        source_tier = int(item.get("source_tier", 3) or 3)
    except (TypeError, ValueError):
        source_tier = 3

    ctype = str(item.get("content_type") or "").strip().casefold()
    expert_deep = bool(item.get("expert_deep_lane"))
    research_signal = bool(item.get("research_signal"))
    interview_signal = bool(item.get("interview_signal")) or _interview_signal(item)

    # A strong domain-specific signal is sufficient for this protected lane;
    # final publication importance remains enforced downstream. Generic
    # interviews without a domain signal still fail the earlier AI-relevance gate.
    if _thematic_signal(item):
        return True

    # A verified expert interview/research item from a high-authority source is
    # intrinsically meaningful enough for this lane; generic interviews are not.
    if source_tier <= 2 and (
        (expert_deep and interview_signal)
        or (research_signal and ctype in {"research", "paper", "study", "experiment"})
    ):
        return True

    features = build_future_features(item)
    strong_dimensions = (
        "capability_shift", "breakthrough", "cross_domain_impact",
        "strategic_implication", "research_depth", "human_societal_impact",
        "future_horizon", "insight_density",
    )
    qualifying = sum(1 for key in strong_dimensions if float(features.get(key, 0.0) or 0.0) >= 0.34)
    return qualifying >= 2


def _interview_signal(item: dict[str, Any]) -> bool:
    content_type = str(item.get("content_type") or "").strip().casefold()
    source_type = str(item.get("source_type") or item.get("type") or item.get("format") or "").strip().casefold()
    text = _text(item)
    return content_type in INTERVIEW_TYPES or source_type in INTERVIEW_TYPES or any(re.search(pattern, text) for pattern in INTERVIEW_SIGNAL_TERMS)


def is_mind_ideas_voices_candidate(item: dict[str, Any]) -> bool:
    """Eligibility gate only; deliberately does not reference a normal score floor."""
    if str(item.get("content_type") or "").strip().casefold() == "education":
        return False
    if not _trusted_source(item):
        return False
    if item.get("protected_slot") or item.get("_rank_is_tier0"):
        return False
    mission = _mission(item)
    thematic = _thematic_signal(item)
    registry_person = _named_registry_person(item)
    explicit_person = _explicit_person_signal(item)
    interview = _interview_signal(item)
    if not _ai_relevant(item):
        return False
    if thematic:
        return True
    # Eligibility identifies valid candidates for this lane. Final publication
    # importance is enforced later by the production publication gate, so valid
    # AI interviews/podcasts and strong thematic signals must remain discoverable.
    # The Mind lane is first-class only for actual mind/awareness content or
    # an identifiable expert voice. Generic forum/programming videos must not
    # consume its single publication slot merely because they are labelled
    # interviews or podcasts.
    person_identity = registry_person or any(
        str(item.get(key) or "").strip()
        for key in ("watch_person", "person", "person_name", "leader", "leader_name", "expert", "expert_name", "author", "speaker", "guest", "interviewee", "researcher")
    )
    if mission in {"mind_cognition", "mind"}:
        return thematic or person_identity
    if interview and (registry_person or person_identity or thematic):
        return True
    if not _importance_evidence(item):
        return False
    if item.get("research_signal") and str(item.get("content_type") or "").strip().casefold() in {
        "research", "paper", "study", "experiment"
    }:
        return True
    if str(item.get("editorial_class") or "").strip().casefold() in {
        "research_breakthrough", "convergence_signal", "leader_interview", "major_industry_news"
    }:
        return True
    return mission in {"future", "future_governance", "convergence", "ai", "ai_core", "mind"} and (
        registry_person or explicit_person
    )


def mind_ideas_voices_score(item: dict[str, Any]) -> float:
    """Independent 0-100 relevance/value score for the second publication domain."""
    score = 0.0
    mission = _mission(item)
    content_type = str(item.get("content_type") or "").strip().casefold()
    thematic = _thematic_signal(item)
    registry_person = _named_registry_person(item)
    explicit_person = _explicit_person_signal(item)
    if mission == "mind_cognition":
        score += 42.0
    elif mission == "mind":
        score += 38.0
    elif mission in {"future", "future_governance", "convergence"}:
        score += 28.0
    elif mission in {"ai", "ai_core"}:
        score += 18.0
    if thematic:
        score += 24.0
    if registry_person:
        score += 18.0
    elif explicit_person:
        score += 14.0
    if content_type in INTERVIEW_TYPES:
        score += 10.0
    try:
        source_tier = int(item.get("source_tier", 3) or 3)
    except (TypeError, ValueError):
        source_tier = 3
    score += {1: 8.0, 2: 5.0, 3: 1.0}.get(source_tier, 0.0)
    if str(item.get("source_type") or "").casefold() in {"official", "university", "scientific", "specialist"}:
        score += 4.0
    return round(min(100.0, score), 2)


def choose_additive_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_ids: set[int],
    max_rank: int = SPECIAL_RANK_WINDOW,
    max_items: int | None = SPECIAL_MAX_PER_PERIOD,
) -> list[dict[str, Any]]:
    """Select second-lane candidates using only the independent lane score.

    ``max_rank`` applies to the lane's own ranking, not ``normal_period_rank``.
    No NORMAL_SCORE_FLOOR or other normal-news score threshold is applied.
    """
    eligible: list[dict[str, Any]] = []
    for item in candidates:
        if id(item) in existing_ids or not is_mind_ideas_voices_candidate(item):
            continue
        item["mind_editorial_score"] = mind_ideas_voices_score(item)
        if float(item["mind_editorial_score"]) < MIND_IDEAS_VOICES_SCORE_FLOOR:
            continue
        eligible.append(item)
    eligible.sort(key=lambda item: (-float(item.get("mind_editorial_score", 0.0) or 0.0), str(item.get("published") or "")),)
    selected = (
        eligible[:max(0, max_rank)]
        if max_items is None
        else eligible[:max(0, max_items)]
    )
    for index, item in enumerate(selected, start=1):
        item["mind_period_rank"] = index
        item["period_rank"] = 1000 + index
        item["normal_period_rank"] = None
        item["protected_editorial_lane"] = "mind_ideas_voices"
        item["mind_lane_selected"] = True
        item["protected_content"] = True
        item["protected_lane_reason"] = "independent_mind_ideas_voices_score"
    return selected


def choose_additive_candidate(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_ids: set[int],
    max_rank: int = SPECIAL_RANK_WINDOW,
) -> dict[str, Any] | None:
    return next(iter(choose_additive_candidates(candidates, existing_ids=existing_ids, max_rank=max_rank, max_items=1)), None)
