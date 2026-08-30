"""Persistent, deterministic Trend Cluster registry.

The registry gives candidate clusters a durable identity without making an LLM
responsible for identity. It is deliberately JSON-serializable so it can live
beside the Radar's existing Git-backed runtime state during this evolution stage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .trend_intelligence import TrendCluster, TrendSignal, lexical_similarity


SCHEMA_VERSION = 1


@dataclass
class ClusterRecord:
    cluster_id: str
    hypothesis: str = ""
    signal_ids: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    parent_cluster_ids: list[str] = field(default_factory=list)
    operation_history: list[dict[str, object]] = field(default_factory=list)


@dataclass
class TrendRegistry:
    schema_version: int = SCHEMA_VERSION
    next_id: int = 1
    clusters: dict[str, ClusterRecord] = field(default_factory=dict)

    @staticmethod
    def _stable_seed(signal: TrendSignal) -> str:
        tokens = sorted(signal.tokens)
        raw = "|".join(tokens[:80]) + "|" + signal.domain
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    def _new_id(self) -> str:
        cluster_id = f"tc-{self.next_id:06d}"
        self.next_id += 1
        return cluster_id

    def _record_operation(self, record: ClusterRecord, operation: str, **payload: object) -> None:
        record.operation_history.append(
            {"operation": operation, "on": date.today().isoformat(), **payload}
        )

    def reconcile(self, candidates: Iterable[TrendCluster]) -> list[ClusterRecord]:
        """Reconcile fresh deterministic candidates against persisted identities.

        Matching uses exact signal overlap first, then conservative lexical
        similarity against prior signals. Existing identities are reused; new
        candidates receive monotonic IDs. No publication decision is made here.
        """
        prior_by_signal: dict[str, ClusterRecord] = {}
        for record in self.clusters.values():
            for signal_id in record.signal_ids:
                prior_by_signal[signal_id] = record

        result: list[ClusterRecord] = []
        for candidate in candidates:
            candidate_ids = {s.signal_id for s in candidate.signals}
            matched = {prior_by_signal[sid] for sid in candidate_ids if sid in prior_by_signal}

            if len(matched) == 1:
                record = next(iter(matched))
            else:
                record = None
                best = 0.0
                candidate_signals = candidate.signals
                for existing in self.clusters.values():
                    if matched and existing in matched:
                        continue
                    prior_ids = set(existing.signal_ids)
                    overlap = len(candidate_ids & prior_ids) / max(1, len(candidate_ids | prior_ids))
                    if overlap > best:
                        best, record = overlap, existing
                if record is None or best < 0.20:
                    record = ClusterRecord(cluster_id=self._new_id())
                    self.clusters[record.cluster_id] = record
                    self._record_operation(record, "create", seed=self._stable_seed(candidate_signals[0]))

            old_ids = set(record.signal_ids)
            record.signal_ids = sorted(old_ids | candidate_ids)
            observed = sorted(s.observed_on.isoformat() for s in candidate.signals)
            if observed:
                record.first_seen = min(filter(None, [record.first_seen, observed[0]]))
                record.last_seen = max(record.last_seen, observed[-1])
            if candidate.signals and not record.hypothesis:
                record.hypothesis = candidate.signals[0].title
            self._record_operation(
                record,
                "reconcile",
                added_signal_ids=sorted(candidate_ids - old_ids),
                signal_count=len(candidate_ids),
            )
            result.append(record)
        return result

    def merge(self, target_id: str, source_id: str) -> ClusterRecord:
        if target_id == source_id:
            raise ValueError("cannot merge a cluster with itself")
        target = self.clusters[target_id]
        source = self.clusters[source_id]
        target.signal_ids = sorted(set(target.signal_ids) | set(source.signal_ids))
        target.parent_cluster_ids = sorted(set(target.parent_cluster_ids + [source_id]))
        self._record_operation(target, "merge", source_cluster_id=source_id)
        del self.clusters[source_id]
        return target

    def split(self, cluster_id: str, groups: list[list[str]]) -> list[ClusterRecord]:
        if len(groups) < 2:
            raise ValueError("split requires at least two groups")
        source = self.clusters[cluster_id]
        source_ids = set(source.signal_ids)
        if any(not set(group) <= source_ids for group in groups):
            raise ValueError("split group contains an unknown signal")
        records: list[ClusterRecord] = []
        for group in groups:
            record = ClusterRecord(
                cluster_id=self._new_id(),
                hypothesis=source.hypothesis,
                signal_ids=sorted(set(group)),
                first_seen=source.first_seen,
                last_seen=source.last_seen,
                parent_cluster_ids=[cluster_id],
            )
            self._record_operation(record, "split_from", source_cluster_id=cluster_id)
            self.clusters[record.cluster_id] = record
            records.append(record)
        self._record_operation(source, "split", child_cluster_ids=[r.cluster_id for r in records])
        del self.clusters[cluster_id]
        return records

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "next_id": self.next_id,
            "clusters": {key: asdict(value) for key, value in self.clusters.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "TrendRegistry":
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported trend registry schema")
        raw_clusters = payload.get("clusters", {})
        if not isinstance(raw_clusters, dict):
            raise ValueError("invalid clusters payload")
        registry = cls(schema_version=SCHEMA_VERSION, next_id=int(payload.get("next_id", 1)))
        for key, raw in raw_clusters.items():
            if not isinstance(raw, dict):
                raise ValueError("invalid cluster record")
            registry.clusters[str(key)] = ClusterRecord(**raw)
        return registry

    @classmethod
    def load(cls, path: str | Path) -> "TrendRegistry":
        file_path = Path(path)
        if not file_path.exists():
            return cls()
        with file_path.open("r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    def save(self, path: str | Path) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = file_path.with_suffix(file_path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(file_path)
