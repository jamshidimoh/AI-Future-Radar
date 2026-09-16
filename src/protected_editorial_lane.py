"""Bounded additive Mind/Ideas/Voices lane for production selection."""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from src.editorial_quality_policy import NORMAL_SCORE_FLOOR

INTERVIEW_TYPES = {
    "interview",
    "podcast",
    "talk",
    "lecture",
    "fireside",
    "conversation",
    "discussion",
    "q&a",
}
_SIGNAL_PATTERNS = (
    r"\bconsciousness\b",
    r"\bartificial consciousness\b",
    r"\bmachine consciousness\b",
    r"\bself-awareness\b",
    r"\bsentience\b",
    r"\bqualia\b",
    r"\bcognitive science\b",
    r"\bphilosophy of mind\b",
    r"\bphilosophy of science\b",
    r"\bphilosophy of technology\b",
    r"\bphilosophy of ai\b",
    r"\bepistemology of ai\b",
    r"\bawareness\b",
    r"\bcognition\b",
)


def _text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "summary", "description", "mission_area", "content_type", "tags", "keywords")
    ).casefold()


def _score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "editorial_score", "mission_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
        if value:
            return value
    return 0.0


def is_mind_ideas_voices_candidate(item: dict[str, Any]) -> bool:
    if str(item.get("content_type") or "").strip().casefold() == "education":
        return False
    source_text = " ".join(
        str(item.get(key) or "")
        for key in ("source", "source_name", "source_type", "source_domain")
    ).casefold()
    if "reddit" in source_text or "community" in source_text:
        return False
    if item.get("protected_slot") or item.get("_rank_is_tier0"):
        return False
    mission = str(item.get("mission_area") or item.get("category") or "").strip().casefold()
    if mission in {"mind", "mind_cognition"}:
        return True
    content_type = str(item.get("content_type") or "").strip().casefold()
    if content_type in INTERVIEW_TYPES:
        return True
    return any(re.search(pattern, _text(item)) for pattern in _SIGNAL_PATTERNS)


def choose_additive_candidate(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_ids: set[int],
    max_rank: int,
    minimum_score: float = NORMAL_SCORE_FLOOR,
) -> dict[str, Any] | None:
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
    return min(eligible, key=lambda item: (int(item.get("normal_period_rank", 999) or 999), -_score(item))) if eligible else None
