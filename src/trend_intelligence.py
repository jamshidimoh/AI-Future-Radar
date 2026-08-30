"""Deterministic, dependency-light Trend Intelligence primitives.

This module deliberately does not call an LLM. It creates reproducible candidate
clusters from normalized signals and keeps source independence separate from
source tier and evidence strength. Production orchestration can adopt it behind
a feature flag without changing publication contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import exp
import re
from typing import Iterable, Sequence

_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]{3,}", re.UNICODE)


@dataclass(frozen=True)
class TrendSignal:
    signal_id: str
    title: str
    summary: str = ""
    source_id: str = ""
    source_tier: str = "T3"
    evidence_level: str = "community_discovery"
    domain: str = "emerging_technology"
    observed_on: date = field(default_factory=date.today)
    novelty: float = 0.0
    strategic_impact: float = 0.0
    evidence_strength: float = 0.0
    mission_relevance: float = 0.0

    @property
    def tokens(self) -> frozenset[str]:
        return frozenset(_TOKEN_RE.findall(f"{self.title} {self.summary}".lower()))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def lexical_similarity(left: TrendSignal, right: TrendSignal) -> float:
    """Return deterministic Jaccard similarity over normalized lexical tokens."""
    a, b = left.tokens, right.tokens
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def temporal_weight(left: TrendSignal, right: TrendSignal, half_life_days: float = 180.0) -> float:
    days = abs((left.observed_on - right.observed_on).days)
    return exp(-days / half_life_days)


def signal_score(signal: TrendSignal) -> float:
    """Score an individual signal without using source tier as a proxy for evidence."""
    value = (
        0.20 * _clamp(signal.novelty)
        + 0.25 * _clamp(signal.evidence_strength)
        + 0.15 * _clamp(signal.mission_relevance)
        + 0.15 * _clamp(signal.strategic_impact)
        + 0.25 * _clamp(1.0 if signal.source_id else 0.0)
    )
    return round(_clamp(value), 4)


@dataclass
class TrendCluster:
    cluster_id: str
    signals: list[TrendSignal] = field(default_factory=list)

    @property
    def signal_count(self) -> int:
        return len(self.signals)

    @property
    def independent_source_count(self) -> int:
        return len({s.source_id for s in self.signals if s.source_id})

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(sorted({s.domain for s in self.signals if s.domain}))

    @property
    def supporting_evidence_count(self) -> int:
        return sum(s.evidence_strength >= 0.5 for s in self.signals)

    @property
    def counter_evidence_count(self) -> int:
        # A negative/contradictory signal is represented by evidence_strength < 0.
        return sum(s.evidence_strength < 0 for s in self.signals)

    @property
    def state(self) -> str:
        if self.counter_evidence_count > self.supporting_evidence_count:
            return "disconfirmed"
        if self.signal_count >= 5 and self.independent_source_count >= 3:
            return "accelerating"
        if self.signal_count >= 3 and self.independent_source_count >= 2:
            return "emerging"
        return "weak_signal"

    @property
    def trend_score(self) -> float:
        if not self.signals:
            return 0.0
        persistence = min(1.0, len({s.observed_on for s in self.signals}) / 4)
        independence = min(1.0, self.independent_source_count / 4)
        evidence = sum(max(0.0, s.evidence_strength) for s in self.signals) / len(self.signals)
        novelty = sum(max(0.0, s.novelty) for s in self.signals) / len(self.signals)
        convergence = min(1.0, len(self.domains) / 3)
        counter_penalty = min(1.0, self.counter_evidence_count / max(1, self.signal_count))
        score = (
            0.15 * novelty
            + 0.20 * persistence
            + 0.20 * independence
            + 0.15 * evidence
            + 0.10 * convergence
            - 0.15 * counter_penalty
        )
        return round(_clamp(score), 4)


def build_clusters(
    signals: Sequence[TrendSignal],
    similarity_threshold: float = 0.42,
) -> list[TrendCluster]:
    """Build stable greedy candidate clusters from normalized signals.

    The algorithm is intentionally conservative and deterministic. It is a first
    evolution-layer primitive; production adoption should add persistent cluster
    IDs and explicit merge/split history rather than replacing this contract with
    opaque LLM decisions.
    """
    ordered = sorted(signals, key=lambda item: (item.observed_on, item.signal_id))
    clusters: list[TrendCluster] = []
    for signal in ordered:
        best: TrendCluster | None = None
        best_score = 0.0
        for cluster in clusters:
            similarity = max((lexical_similarity(signal, existing) for existing in cluster.signals), default=0.0)
            temporal = max((temporal_weight(signal, existing) for existing in cluster.signals), default=0.0)
            combined = similarity * (0.7 + 0.3 * temporal)
            if combined >= similarity_threshold and combined > best_score:
                best, best_score = cluster, combined
        if best is None:
            cluster_id = f"tc-{len(clusters) + 1:04d}"
            clusters.append(TrendCluster(cluster_id=cluster_id, signals=[signal]))
        else:
            best.signals.append(signal)
    return clusters


def cluster_summary(cluster: TrendCluster) -> dict[str, object]:
    """Return a serializable audit summary for observability and tests."""
    return {
        "cluster_id": cluster.cluster_id,
        "signal_count": cluster.signal_count,
        "independent_source_count": cluster.independent_source_count,
        "domains": list(cluster.domains),
        "state": cluster.state,
        "trend_score": cluster.trend_score,
        "signal_ids": [s.signal_id for s in cluster.signals],
    }
