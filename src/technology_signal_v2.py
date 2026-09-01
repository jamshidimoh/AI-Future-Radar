"""P3 technology-signal score.

The signal layer intentionally excludes editorial suitability features. Raw
freshness/source/leader metrics remain available in the signal vector as
observations, but they do not contribute to the canonical technology signal
score.
"""
from __future__ import annotations

from typing import Mapping

WEIGHTS = {
    "novelty": 0.25,
    "future_impact": 0.25,
    "technical_significance": 0.20,
    "strategic_relevance": 0.15,
    "trend_alignment": 0.15,
}


def calculate_technology_signal_score(vector: Mapping[str, float]) -> float:
    return round(sum(max(0.0, min(10.0, float(vector.get(k, 0.0)))) * w for k, w in WEIGHTS.items()) * 10.0, 2)
