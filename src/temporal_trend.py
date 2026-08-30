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


def _period_key(period: str) -> tuple[int, int]:
    """Parse canonical YYYY-MM periods and reject ambiguous ordering."""
    try:
        year_text, month_text = period.split("-", 1)
        year, month = int(year_text), int(month_text)
    except (AttributeError, ValueError) as exc:
        raise ValueError("period must use YYYY-MM format") from exc
    if not 1 <= month <= 12 or year < 1:
        raise ValueError("period must use a valid YYYY-MM value")
    return year, month


def assess(observations: Iterable[TrendObservation]) -> TemporalAssessment:
    rows = list(observations)
    if not rows:
        raise ValueError("at least one observation is required")
    if any(o.score < 0 or o.score > 1 for o in rows):
        raise ValueError("score must be between 0 and 1")
    if any(o.evidence_count < 0 or o.independent_sources < 0 for o in rows):
        raise ValueError("observation counts cannot be negative")
    periods = [_period_key(o.period) for o in rows]
    if any(current <= previous for previous, current in zip(periods, periods[1:])):
        raise ValueError("observations must be in strictly increasing period order")
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
