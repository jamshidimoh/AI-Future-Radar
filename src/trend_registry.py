"""Persistent, deterministic Trend Cluster registry.

The registry gives candidate clusters a durable identity without making an LLM
responsible for identity. It keeps lightweight signal fingerprints so recurring
clusters can be reconciled even when an upstream signal receives a new ID.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .trend_intelligence import TrendCluster, TrendSignal, lexical_similarity


SCHEMA_VERSION = 2
RECONCILE_SIMILARITY = 0.72


@dataclass
class ClusterRecord:
    cluster_id: str
    hypothesis: str = ""
    signal_ids: list[str] = field(default_factory=list)
    signal_fingerprints: dict[str, dict[str, object]] = field(default_factory=dict)
    first_seen: str = ""
    last_seen: str = ""
    parent_cluster_ids: list[str] = field(default_factory=list)
    status: str = "active"
    superseded_by: list[str] = field(default_factory=list)
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

    @staticmethod
    def _fingerprint(signal: TrendSignal) -> dict[str, object]:
        return {
            "tokens": sorted(signal.tokens),
            "domain": signal.domain,
            "source_id": signal.source_id,
        }

    @staticmethod
    def _signal_from_fingerprint(signal_id: str, fingerprint: dict[str, object]) -> TrendSignal:
        tokens = fingerprint.get("tokens", [])
        text = " ".join(str(token) for token in tokens) if isinstance(tokens, list) else ""
        return TrendSignal(
            signal_id=signal_id,
            title=text,
            summary=text,
            source_id=str(fingerprint.get("source_id", "")),
            domain=str(fingerprint.get("domain", "emerging_technology")),
        )

    def _new_id(self) -> str:
        cluster_id = f"tc-{self.next_id:06d}"
        self.next_id += 1
        return cluster_id

    def _record_operation(self, record: ClusterRecord, operation: str, **payload: object) -> None:
        record.operation_history.append(
            {"operation": operation, "on": date.today().isoformat(), **payload}
        )

    def _best_existing_match(self, candidate: TrendCluster) -> ClusterRecord | None:
        best_record: ClusterRecord | None = None
        best_score = 0.0
        for record in self.clusters.values():
            if record.status != "active" or not record.signal_fingerprints:
                continue
            similarities: list[float] = []
            for signal in candidate.signals:
                prior_signals = (
                    self._signal_from_fingerprint(signal_id, fingerprint)
                    for signal_id, fingerprint in record.signal_fingerprints.items()
                )
                similarities.extend(lexical_similarity(signal, prior) for prior in prior_signals)
            score = max(similarities, default=0.0)
            if score > best_score:
                best_score, best_record = score, record
        return best_record if best_score >= RECONCILE_SIMILARITY else None

    def reconcile(self, candidates: Iterable[TrendCluster]) -> list[ClusterRecord]:
        """Reconcile fresh candidates against durable identities.

        Exact signal overlap is preferred. If an upstream signal receives a new
        ID, a conservative lexical fingerprint match may reuse the existing
        identity. No publication decision is made here.
        """
        prior_by_signal: dict[str, ClusterRecord] = {}
        for record in self.clusters.values():
            if record.status != "active":
                continue
            for signal_id in record.signal_ids:
                prior_by_signal[signal_id] = record

        result: list[ClusterRecord] = []
        for candidate in candidates:
            if not candidate.signals:
                continue
            candidate_ids = {s.signal_id for s in candidate.signals}
            matched = {prior_by_signal[sid] for sid in candidate_ids if sid in prior_by_signal}
            record = next(iter(matched)) if len(matched) == 1 else self._best_existing_match(candidate)

            if record is None:
                record = ClusterRecord(cluster_id=self._new_id())
                self.clusters[record.cluster_id] = record
                self._record_operation(record, "create", seed=self._stable_seed(candidate.signals[0]))

            old_ids = set(record.signal_ids)
            for signal in candidate.signals:
                record.signal_fingerprints[signal.signal_id] = self._fingerprint(signal)
            record.signal_ids = sorted(set(record.signal_ids) | candidate_ids)
            observed = sorted(s.observed_on.isoformat() for s in candidate.signals)
            if observed:
                existing_dates = [d for d in (record.first_seen, record.last_seen) if d]
                record.first_seen = min(existing_dates + [observed[0]])
                record.last_seen = max(existing_dates + [observed[-1]])
            if candidate.signals and not record.hypothesis:
                record.hypothesis = candidate.signals[0].title
            self._record_operation(
                record,
                "reconcile",
                added_signal_ids=sorted(candidate_ids - old_ids),
                signal_count=len(record.signal_ids),
            )
            result.append(record)
        return result

    def merge(self, target_id: str, source_id: str) -> ClusterRecord:
        if target_id == source_id:
            raise ValueError("cannot merge a cluster with itself")
        target = self.clusters[target_id]
        source = self.clusters[source_id]
        target.signal_ids = sorted(set(target.signal_ids) | set(source.signal_ids))
        target.signal_fingerprints.update(source.signal_fingerprints)
        target.parent_cluster_ids = sorted(set(target.parent_cluster_ids + [source_id]))
        source.status = "merged"
        source.superseded_by = [target_id]
        self._record_operation(target, "merge", source_cluster_id=source_id)
        self._record_operation(source, "merged_into", target_cluster_id=target_id)
        return target

    def split(self, cluster_id: str, groups: list[list[str]]) -> list[ClusterRecord]:
        if len(groups) < 2:
            raise ValueError("split requires at least two groups")
        source = self.clusters[cluster_id]
        source_ids = set(source.signal_ids)
        if any(not set(group) <= source_ids for group in groups):
            raise ValueError("split group contains an unknown signal")
        if len(set().union(*(set(group) for group in groups))) != len(source_ids):
            raise ValueError("split groups must cover every source signal")
        records: list[ClusterRecord] = []
        for group in groups:
            record = ClusterRecord(
                cluster_id=self._new_id(),
                hypothesis=source.hypothesis,
                signal_ids=sorted(set(group)),
                signal_fingerprints={sid: source.signal_fingerprints[sid] for sid in group},
                first_seen=source.first_seen,
                last_seen=source.last_seen,
                parent_cluster_ids=[cluster_id],
            )
            self._record_operation(record, "split_from", source_cluster_id=cluster_id)
            self.clusters[record.cluster_id] = record
            records.append(record)
        source.status = "split"
        source.superseded_by = [r.cluster_id for r in records]
        self._record_operation(source, "split", child_cluster_ids=[r.cluster_id for r in records])
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
