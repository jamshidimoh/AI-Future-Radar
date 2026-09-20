"""Deterministic topic novelty and information-gain helpers for Radar portfolio selection."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

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


def _signature(value: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(value, dict):
        try:
            from src.semantic_dedup import get_story_signature
            return get_story_signature(value)
        except Exception:
            return {}
    raw = str(value or "")
    marker = "__semantic_story__:"
    if raw.startswith(marker):
        try:
            parsed = json.loads(raw[len(marker):])
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    try:
        from src.semantic_dedup import get_story_signature
        return get_story_signature(raw)
    except Exception:
        return {}


def entity_overlap(a: dict[str, Any] | str, b: dict[str, Any] | str) -> float:
    """Return a bounded entity-overlap score for soft editorial diversity control."""
    left = _signature(a)
    right = _signature(b)
    left_entities = set(left.get("anchors") or []) | set(left.get("personnel") or [])
    right_entities = set(right.get("anchors") or []) | set(right.get("personnel") or [])
    leader_left = str(left.get("leader") or "").strip()
    leader_right = str(right.get("leader") or "").strip()
    if leader_left and leader_right and leader_left == leader_right:
        return 1.0
    if not left_entities or not right_entities:
        return 0.0
    return round(len(left_entities & right_entities) / max(1, len(left_entities | right_entities)), 4)


def leader_overlap(a: dict[str, Any] | str, b: dict[str, Any] | str) -> bool:
    left = _signature(a)
    right = _signature(b)
    la = str(left.get("leader") or "").strip()
    lb = str(right.get("leader") or "").strip()
    return bool(la and lb and la == lb)


def max_entity_overlap(item: dict[str, Any], selected: Iterable[dict[str, Any]]) -> float:
    return max((entity_overlap(item, other) for other in selected), default=0.0)


def max_history_entity_overlap(item: dict[str, Any], history_signatures: Iterable[dict[str, Any] | str]) -> float:
    return max((entity_overlap(item, other) for other in history_signatures), default=0.0)


def max_history_topic_similarity(item: dict[str, Any], history_signatures: Iterable[dict[str, Any] | str]) -> float:
    return max(
        (
            topic_similarity(
                item,
                _signature(other) if isinstance(other, str) else other,
            )
            for other in history_signatures
        ),
        default=0.0,
    )


def editorial_novelty_score(
    item: dict[str, Any],
    selected: Iterable[dict[str, Any]],
    history_signatures: Iterable[dict[str, Any] | str] = (),
) -> dict[str, float]:
    """Expose explainable novelty signals without making them hard rejection gates."""
    current_topic = max_topic_similarity(item, selected)
    current_entity = max_entity_overlap(item, selected)
    history_topic = max_history_topic_similarity(item, history_signatures)
    history_entity = max_history_entity_overlap(item, history_signatures)
    return {
        "current_topic_similarity": round(current_topic, 4),
        "current_entity_overlap": round(current_entity, 4),
        "history_topic_similarity": round(history_topic, 4),
        "history_entity_overlap": round(history_entity, 4),
        "novelty": round(1.0 - max(current_topic, history_topic), 4),
    }


def portfolio_value_with_history(
    item: dict[str, Any],
    selected: Iterable[dict[str, Any]],
    history_signatures: Iterable[dict[str, Any] | str] = (),
    *,
    diversity_weight: float = 8.0,
    similarity_penalty: float = 12.0,
    entity_repeat_penalty: float = 7.0,
    leader_repeat_penalty: float = 10.0,
    history_topic_penalty: float = 5.0,
    history_entity_penalty: float = 4.0,
) -> float:
    """Quality-first portfolio value with bounded current/history saturation penalties."""
    value = portfolio_value(
        item,
        selected,
        diversity_weight=diversity_weight,
        similarity_penalty=similarity_penalty,
    )
    current_entity = max_entity_overlap(item, selected)
    leader_repeat = any(leader_overlap(item, other) for other in selected)
    history_topic = max_history_topic_similarity(item, history_signatures)
    history_entity = max_history_entity_overlap(item, history_signatures)
    value -= entity_repeat_penalty * current_entity
    if leader_repeat:
        value -= leader_repeat_penalty
    value -= history_topic_penalty * history_topic
    value -= history_entity_penalty * history_entity
    return round(value, 4)
