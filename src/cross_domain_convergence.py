"""Deterministic cross-domain convergence primitives for Trend Intelligence."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable


@dataclass(frozen=True)
class DomainTrend:
    trend_id: str
    domain: str
    score: float
    evidence_count: int


@dataclass(frozen=True)
class MetaTrend:
    trend_ids: tuple[str, ...]
    domains: tuple[str, ...]
    convergence_score: float


def detect_convergence(trends: Iterable[DomainTrend], *, min_domains: int = 2, min_score: float = 0.60) -> list[MetaTrend]:
    rows = list(trends)
    if min_domains < 2:
        raise ValueError("min_domains must be at least 2")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1")
    groups: dict[str, list[DomainTrend]] = {}
    for trend in rows:
        if not trend.trend_id or not trend.domain:
            raise ValueError("trend_id and domain are required")
        if not 0.0 <= trend.score <= 1.0 or trend.evidence_count < 0:
            raise ValueError("invalid trend observation")
        groups.setdefault(trend.domain, []).append(trend)

    candidates: list[MetaTrend] = []
    domains = sorted(groups)
    for left, right in combinations(domains, 2):
        best: tuple[float, DomainTrend, DomainTrend] | None = None
        for a in groups[left]:
            for b in groups[right]:
                score = min(a.score, b.score) * min(1.0, (a.evidence_count + b.evidence_count) / 10.0)
                if best is None or score > best[0]:
                    best = score, a, b
        if best and best[0] >= min_score:
            score, a, b = best
            candidates.append(MetaTrend((a.trend_id, b.trend_id), (left, right), score))
    return candidates
