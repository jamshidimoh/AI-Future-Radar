"""Independent editorial scoring model used behind an explicit feature contract.

The model intentionally separates topic/mission routing from evidence and impact.
All inputs are normalized to 0..1 and the weighted sum returns a 0..100 score.
"""
from __future__ import annotations

from typing import Any


def _clip(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def score_features(features: dict[str, Any]) -> dict[str, float]:
    return {
        "evidence": _clip(features.get("evidence")),
        "impact": _clip(features.get("impact")),
        "novelty": _clip(features.get("novelty")),
        "future_relevance": _clip(features.get("future_relevance")),
        "strategic_relevance": _clip(features.get("strategic_relevance")),
        "source_quality": _clip(features.get("source_quality")),
    }


WEIGHTS = {
    "evidence": 0.22,
    "impact": 0.20,
    "novelty": 0.16,
    "future_relevance": 0.16,
    "strategic_relevance": 0.14,
    "source_quality": 0.12,
}


def editorial_score_v2(features: dict[str, Any]) -> float:
    normalized = score_features(features)
    return round(sum(normalized[name] * weight for name, weight in WEIGHTS.items()) * 100.0, 2)
