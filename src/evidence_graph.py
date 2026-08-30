from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    claim_id: str
    polarity: str
    strength: float = 0.0
    publisher: str | None = None

    def __post_init__(self) -> None:
        if self.polarity not in {"supporting", "counter"}:
            raise ValueError("polarity must be 'supporting' or 'counter'")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be between 0 and 1")


class EvidenceGraph:
    def __init__(self) -> None:
        self._items: dict[str, Evidence] = {}
        self._by_claim: dict[str, list[str]] = defaultdict(list)

    def add(self, evidence: Evidence) -> None:
        existing = self._items.get(evidence.evidence_id)
        if existing is not None:
            if existing != evidence:
                raise ValueError(f"conflicting evidence id: {evidence.evidence_id}")
            return
        self._items[evidence.evidence_id] = evidence
        self._by_claim[evidence.claim_id].append(evidence.evidence_id)

    def extend(self, evidences: list[Evidence]) -> None:
        for evidence in evidences:
            self.add(evidence)

    def _claim_items(self, claim_id: str) -> list[Evidence]:
        return [self._items[eid] for eid in self._by_claim.get(claim_id, [])]

    def supporting(self, claim_id: str) -> list[Evidence]:
        return [e for e in self._claim_items(claim_id) if e.polarity == "supporting"]

    def counter(self, claim_id: str) -> list[Evidence]:
        return [e for e in self._claim_items(claim_id) if e.polarity == "counter"]

    def independent_source_count(self, claim_id: str) -> int:
        return len({e.publisher or e.source for e in self._claim_items(claim_id)})

    def net_evidence(self, claim_id: str) -> float:
        supporting = sum(e.strength for e in self.supporting(claim_id))
        counter = sum(e.strength for e in self.counter(claim_id))
        total = supporting + counter
        return (supporting - counter) / total if total else 0.0
