"""Deterministic evidence graph primitives for Trend Intelligence.

The graph deliberately separates source identity, claims, evidence and
counter-evidence.  It does not infer scientific truth and does not use an
LLM; downstream scoring can consume these auditable records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Literal

EvidenceKind = Literal["supporting", "counter"]


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_id: str
    claim_id: str
    kind: EvidenceKind
    strength: float = 0.5
    independence_group: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.source_id or not self.claim_id:
            raise ValueError("evidence_id, source_id and claim_id are required")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be between 0 and 1")


@dataclass
class EvidenceGraph:
    evidences: Dict[str, Evidence] = field(default_factory=dict)

    def add(self, evidence: Evidence) -> None:
        existing = self.evidences.get(evidence.evidence_id)
        if existing is not None and existing != evidence:
            raise ValueError(f"conflicting evidence id: {evidence.evidence_id}")
        self.evidences[evidence.evidence_id] = evidence

    def extend(self, evidences: Iterable[Evidence]) -> None:
        for evidence in evidences:
            self.add(evidence)

    def supporting(self, claim_id: str | None = None) -> List[Evidence]:
        return self._by_kind("supporting", claim_id)

    def counter(self, claim_id: str | None = None) -> List[Evidence]:
        return self._by_kind("counter", claim_id)

    def _by_kind(self, kind: EvidenceKind, claim_id: str | None) -> List[Evidence]:
        return [
            e for e in self.evidences.values()
            if e.kind == kind and (claim_id is None or e.claim_id == claim_id)
        ]

    def independent_source_count(self, claim_id: str | None = None) -> int:
        rows = [
            e for e in self.evidences.values()
            if claim_id is None or e.claim_id == claim_id
        ]
        groups = {e.independence_group or e.source_id for e in rows}
        return len(groups)

    def net_evidence(self, claim_id: str | None = None) -> float:
        supporting = sum(e.strength for e in self.supporting(claim_id))
        counter = sum(e.strength for e in self.counter(claim_id))
        total = supporting + counter
        return 0.0 if total == 0 else (supporting - counter) / total
