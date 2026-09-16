"""Bounded additive Mind/Ideas/Voices lane for production selection.

The lane is deliberately additive to the normal three-item portfolio. It can
surface up to two extra, already-ranked candidates per production iteration
when they match influential people/ideas, specialist conversations, or
AI-relevant mind/science/future interdisciplinary themes.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from src.editorial_quality_policy import NORMAL_SCORE_FLOOR

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = ROOT / "config" / "pioneers.yaml"
INTERVIEW_TYPES = {
    "interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a",
}
MISSION_AREAS = {"mind", "mind_cognition", "future", "future_governance", "convergence", "ai", "ai_core"}
_SPECIAL_SIGNAL_PATTERNS = (
    r"\bconsciousness\b", r"\bartificial consciousness\b", r"\bmachine consciousness\b",
    r"\bself-awareness\b", r"\bsentience\b", r"\bqualia\b", r"\bcognitive science\b",
    r"\bphilosophy of mind\b", r"\bphilosophy of science\b", r"\bphilosophy of technology\b",
    r"\bphilosophy of ai\b", r"\bepistemology of ai\b", r"\bawareness\b", r"\bcognition\b",
    r"\bneuroscience\b", r"\bneurotechnology\b", r"\bbrain-computer interface\b", r"\bbrain-computer\b",
    r"\bgenomics\b", r"\bgenetic\b", r"\bgene editing\b", r"\bsynthetic biology\b",
    r"\bfuturology\b", r"\bfutures? research\b", r"\bforesight\b", r"\bfuture studies\b",
    r"\bsociology\b", r"\bsocial science\b", r"\banthropology\b", r"\bsociety and technology\b", r"\btechnology and society\b",
)
PERSON_KEYS = (
    "watch_person", "person", "person_name", "leader", "leader_name", "expert", "expert_name",
    "author", "speaker", "guest", "interviewee", "researcher",
)


def _text(item: dict[str, Any]) -> str:
    fields = ("title", "summary", "description", "mission_area", "content_type", "tags", "keywords", *PERSON_KEYS)
    return " ".join(str(item.get(key) or "") for key in fields).casefold()


def _score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "editorial_score", "mission_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
        if value:
            return value
    return 0.0


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
    values = [str(item.get(key) or "").strip().casefold() for key in PERSON_KEYS]
    text = _text(item)
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


def is_mind_ideas_voices_candidate(item: dict[str, Any]) -> bool:
    """Return true only for explicit high-value people or specialist thought domains."""
    if str(item.get("content_type") or "").strip().casefold() == "education":
        return False
    if not _trusted_source(item):
        return False
    if item.get("protected_slot") or item.get("_rank_is_tier0"):
        return False

    mission = str(item.get("mission_area") or item.get("category") or "").strip().casefold()
    content_type = str(item.get("content_type") or "").strip().casefold()
    text = _text(item)
    thematic_signal = any(re.search(pattern, text) for pattern in _SPECIAL_SIGNAL_PATTERNS)
    registry_person = _named_registry_person(item)
    explicit_person = _explicit_person_signal(item)

    if mission in {"mind", "mind_cognition"}:
        return True
    if thematic_signal:
        return True
    if content_type in INTERVIEW_TYPES and (registry_person or explicit_person or mission in MISSION_AREAS):
        return True
    if mission in {"future", "future_governance", "convergence", "ai", "ai_core"} and (registry_person or explicit_person):
        return True
    if content_type in {"article", "essay", "analysis", "opinion"} and (registry_person or explicit_person) and mission in MISSION_AREAS:
        return True
    return False


def choose_additive_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_ids: set[int],
    max_rank: int,
    max_items: int = 2,
    minimum_score: float = NORMAL_SCORE_FLOOR,
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for item in candidates:
        if id(item) in existing_ids or not is_mind_ideas_voices_candidate(item):
            continue
        try:
            rank = int(item.get("normal_period_rank", 999) or 999)
        except (TypeError, ValueError):
            rank = 999
        if rank > max_rank or _score(item) < minimum_score:
            continue
        eligible.append(item)
    eligible.sort(key=lambda item: (int(item.get("normal_period_rank", 999) or 999), -_score(item)))
    return eligible[:max(0, max_items)]


def choose_additive_candidate(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_ids: set[int],
    max_rank: int,
    minimum_score: float = NORMAL_SCORE_FLOOR,
) -> dict[str, Any] | None:
    return next(iter(choose_additive_candidates(candidates, existing_ids=existing_ids, max_rank=max_rank, max_items=1, minimum_score=minimum_score)), None)
