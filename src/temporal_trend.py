"""Deterministic temporal state tracking for Trend Intelligence."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class TrendState(str, Enum):
    EMERGING = "emerging"
    ACCELERATING = "accelerating"
    ESTABLISHED = "established"
    STAGNATING = "stagnating"
    FADING = "fading"
    DISCONFIRMED = "disconfirmed"
    REVIVED = "revived"


@dataclass(frozen=True)
class TrendObservation:
    period: str
    score: float
    evidence_count: int
    independent_sources: int


@dataclass(frozen=True)
class TemporalAssessment:
    state: TrendState
    acceleration: float
    evidence_growth: float


def assess(observations: Iterable[TrendObservation]) -> TemporalAssessment:
    rows = list(observations)
    if not rows:
        raise ValueError("at least one observation is required")
    if any(o.score < 0 or o.evidence_count < 0 or o.independent_sources < 0 for o in rows):
        raise ValueError("observation values cannot be negative")
    if len(rows) == 1:
        return TemporalAssessment(TrendState.EMERGING, 0.0, 0.0)

    previous, current = rows[-2], rows[-1]
    acceleration = current.score - previous.score
    evidence_growth = current.evidence_count - previous.evidence_count

    if current.score <= 0 and current.evidence_count == 0:
        state = TrendState.DISCONFIRMED
    elif acceleration > 0.10 and evidence_growth >= 1:
        state = TrendState.ACCELERATING
    elif acceleration > 0:
        state = TrendState.EMERGING
    elif acceleration < -0.10:
        state = TrendState.FADING
    else:
        state = TrendState.STAGNATING

    return TemporalAssessment(state, acceleration, evidence_growth)
