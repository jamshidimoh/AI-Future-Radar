"""Deterministic topic novelty and information-gain helpers for Radar portfolio selection."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable

_GENERIC = {
    "ai", "artificial", "intelligence", "model", "models", "new", "using", "use", "system",
    "systems", "technology", "technologies", "tool", "tools", "platform", "platforms",
    "research", "study", "paper", "news", "future", "digital", "chatgpt", "openai",
}
_STOP = _GENERIC | {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "from", "by",
    "as", "is", "are", "this", "that", "how", "what", "why", "can", "will", "about",
}


def _tokens(item: dict[str, Any]) -> set[str]:
    text = " ".join(str(item.get(k) or "") for k in (
        "title", "summary", "description", "category", "mission_area", "tags", "keywords",
    )).casefold()
    words = re.findall(r"[\w\u0600-\u06ff]{3,}", text)
    return {w for w in words if w not in _STOP and not w.isdigit()}


def topic_fingerprint(item: dict[str, Any]) -> str:
    return " ".join(sorted(_tokens(item)))


def topic_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    sequence = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return max(0.0, min(1.0, 0.65 * jaccard + 0.35 * sequence))


def max_topic_similarity(item: dict[str, Any], selected: Iterable[dict[str, Any]]) -> float:
    return max((topic_similarity(item, other) for other in selected), default=0.0)


def information_gain_score(item: dict[str, Any], selected: Iterable[dict[str, Any]]) -> float:
    """Return 0..100: high means the item adds a distinct topic to the portfolio."""
    novelty = 1.0 - max_topic_similarity(item, selected)
    return round(100.0 * novelty, 3)


def portfolio_value(item: dict[str, Any], selected: Iterable[dict[str, Any]], *, diversity_weight: float = 8.0, similarity_penalty: float = 12.0) -> float:
    """Blend editorial score with bounded novelty; never replaces quality score."""
    try:
        base = float(item.get("final_editorial_score", item.get("editorial_score", item.get("score", 0))) or 0)
    except (TypeError, ValueError):
        base = 0.0
    similarity = max_topic_similarity(item, selected)
    return base + diversity_weight * (1.0 - similarity) - similarity_penalty * similarity
