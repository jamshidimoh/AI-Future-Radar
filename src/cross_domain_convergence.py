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


def detect_convergence(
    trends: Iterable[DomainTrend], *, min_domains: int = 2, min_score: float = 0.60
) -> list[MetaTrend]:
    rows = list(trends)
    if min_domains < 2:
        raise ValueError("min_domains must be at least 2")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1")
    if any(not t.trend_id or not t.domain for t in rows):
        raise ValueError("trend_id and domain are required")
    if any(not 0.0 <= t.score <= 1.0 or t.evidence_count < 0 for t in rows):
        raise ValueError("invalid trend observation")

    groups: dict[str, list[DomainTrend]] = {}
    for trend in rows:
        groups.setdefault(trend.domain, []).append(trend)

    candidates: list[MetaTrend] = []
    domains = sorted(groups)
    for domain_group in combinations(domains, min_domains):
        best: tuple[float, tuple[DomainTrend, ...]] | None = None
        for trends_group in _combinations_by_domain([groups[d] for d in domain_group]):
            score = min(t.score for t in trends_group)
            evidence_factor = min(1.0, sum(t.evidence_count for t in trends_group) / (5 * len(trends_group)))
            score *= evidence_factor
            if best is None or score > best[0]:
                best = score, trends_group
        if best and best[0] >= min_score:
            score, selected = best
            candidates.append(
                MetaTrend(tuple(t.trend_id for t in selected), domain_group, score)
            )
    return candidates


def _combinations_by_domain(groups: list[list[DomainTrend]]) -> Iterable[tuple[DomainTrend, ...]]:
    if not groups:
        return
    if len(groups) == 1:
        yield from ((item,) for item in groups[0])
        return
    for head in groups[0]:
        for tail in _combinations_by_domain(groups[1:]):
            yield (head, *tail)
