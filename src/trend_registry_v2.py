"""G2 persistent trend registry and deterministic lineage reconciliation.

The registry is intentionally publication-decoupled. It stores trend identity,
observations and lineage; it does not modify publication eligibility or ranking.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_CONFIG: dict[str, Any] = {
    "identity_overlap_threshold": 0.50,
    "minimum_shared_members": 1,
    "decay_after_missed_runs": 1,
}

SCHEMA_VERSION = 2
ACTIVE_STATES = {"active", "revived"}


def validate_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(dict(config or {}))
    threshold = float(cfg["identity_overlap_threshold"])
    minimum_shared = int(cfg["minimum_shared_members"])
    decay_after = int(cfg["decay_after_missed_runs"])
    if not 0.0 < threshold <= 1.0:
        raise ValueError("identity_overlap_threshold must be in (0, 1]")
    if minimum_shared < 1:
        raise ValueError("minimum_shared_members must be >= 1")
    if decay_after < 1:
        raise ValueError("decay_after_missed_runs must be >= 1")
    cfg["identity_overlap_threshold"] = threshold
    cfg["minimum_shared_members"] = minimum_shared
    cfg["decay_after_missed_runs"] = decay_after
    return cfg


def empty_registry() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_run_id": None,
        "last_run_index": 0,
        "clusters": {},
        "signal_history": [],
        "lineage": [],
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_new_id(member_ids: Sequence[str], run_index: int) -> str:
    seed = f"{run_index}|{'|'.join(sorted(str(x) for x in member_ids))}"
    return f"trend-g2-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:20]}"


def _member_set(cluster: Mapping[str, Any]) -> set[str]:
    return {str(x) for x in cluster.get("member_ids", []) if str(x)}


def member_overlap(left: Sequence[str], right: Sequence[str]) -> float:
    a = {str(x) for x in left if str(x)}
    b = {str(x) for x in right if str(x)}
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _eligible_previous(current: Mapping[str, Any], registry: Mapping[str, Any], cfg: Mapping[str, Any]) -> list[tuple[float, int, str]]:
    current_ids = _member_set(current)
    candidates: list[tuple[float, int, str]] = []
    for cluster_id, previous in dict(registry.get("clusters") or {}).items():
        if previous.get("state") == "disconfirmed":
            continue
        previous_ids = _member_set(previous)
        shared = len(current_ids & previous_ids)
        overlap = member_overlap(current_ids, previous_ids)
        if shared >= cfg["minimum_shared_members"] and overlap >= cfg["identity_overlap_threshold"]:
            candidates.append((overlap, shared, str(cluster_id)))
    return sorted(candidates, key=lambda x: (-x[0], -x[1], x[2]))


def _choose_primary(candidates: Sequence[tuple[float, int, str]], registry: Mapping[str, Any]) -> str:
    ranked = []
    clusters = dict(registry.get("clusters") or {})
    for overlap, shared, cluster_id in candidates:
        previous = clusters[cluster_id]
        ranked.append(
            (
                overlap,
                shared,
                -int(previous.get("first_seen_run", 0) or 0),
                cluster_id,
            )
        )
    return max(ranked)[3]


def _record_observation(run_id: str, run_index: int, cluster_id: str, cluster: Mapping[str, Any], state: str) -> dict[str, Any]:
    return {
        "run_id": str(run_id),
        "run_index": int(run_index),
        "cluster_id": cluster_id,
        "member_ids": sorted(str(x) for x in cluster.get("member_ids", [])),
        "trend_score": float(cluster.get("trend_score", 0.0) or 0.0),
        "trend_confidence": float(cluster.get("trend_confidence", 0.0) or 0.0),
        "state": state,
    }


def _append_lineage(registry: dict[str, Any], run_id: str, run_index: int, event: str, **payload: Any) -> None:
    event_record = {"run_id": str(run_id), "run_index": int(run_index), "event": event}
    event_record.update(payload)
    registry["lineage"].append(event_record)


def _new_cluster_record(cluster_id: str, cluster: Mapping[str, Any], run_id: str, run_index: int) -> dict[str, Any]:
    member_ids = sorted(str(x) for x in cluster.get("member_ids", []))
    return {
        "cluster_id": cluster_id,
        "first_seen_run": int(run_index),
        "last_seen_run": int(run_index),
        "last_run_id": str(run_id),
        "state": "active",
        "missed_runs": 0,
        "revival_count": 0,
        "disconfirmation_count": 0,
        "member_ids": member_ids,
        "last_observation": _record_observation(run_id, run_index, cluster_id, cluster, "active"),
        "observations": [_record_observation(run_id, run_index, cluster_id, cluster, "active")],
    }


def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    if int(registry.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"unsupported registry schema_version: {registry.get('schema_version')}")
    for key in ("clusters", "signal_history", "lineage"):
        if not isinstance(registry.get(key), (dict, list)):
            raise ValueError(f"registry.{key} has invalid type")
    return dict(registry)


def load_registry(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return empty_registry()
    data = json.loads(target.read_text(encoding="utf-8"))
    return validate_registry(data)


def save_registry(path: str | Path, registry: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_canonical_json(registry) + "\n", encoding="utf-8")


def registry_snapshot(registry: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(_canonical_json(registry))


def reconcile_registry(
    registry: Mapping[str, Any] | None,
    current_clusters: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    run_index: int,
    config: Mapping[str, Any] | None = None,
    disconfirmed_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Reconcile current G1 clusters with persistent G2 identity and lineage.

    Matching is deterministic. Existing identities are retained on sufficient
    member overlap. A previous cluster may feed a split; multiple previous
    clusters may feed a merge. Replays with the same member IDs retain identity.
    Missing clusters decay after the configured miss count. A later match revives
    them. Explicit disconfirmation is terminal; a later reappearance receives a
    fresh identity with a lineage link to the disconfirmed cluster.
    """
    cfg = validate_config(config)
    result = registry_snapshot(registry or empty_registry())
    validate_registry(result)
    if int(run_index) <= int(result.get("last_run_index", 0) or 0):
        raise ValueError("run_index must increase monotonically")

    result["last_run_id"] = str(run_id)
    result["last_run_index"] = int(run_index)
    result.setdefault("clusters", {})
    result.setdefault("signal_history", [])
    result.setdefault("lineage", [])

    previous_clusters = dict(result["clusters"])
    seen_ids: set[str] = set()
    disconfirmed = {str(x) for x in (disconfirmed_ids or [])}
    reconciled: list[dict[str, Any]] = []

    ordered_current = sorted(
        (dict(cluster) for cluster in current_clusters),
        key=lambda cluster: (sorted(str(x) for x in cluster.get("member_ids", [])), str(cluster.get("cluster_id", ""))),
    )

    for current in ordered_current:
        current_members = sorted(str(x) for x in current.get("member_ids", []))
        candidates = _eligible_previous(current, result, cfg)
        exact = [candidate for candidate in candidates if set(current_members) == _member_set(previous_clusters[candidate[2]])]
        if exact:
            primary_id = _choose_primary(exact, result)
        elif candidates:
            primary_id = _choose_primary(candidates, result)
        else:
            primary_id = _stable_new_id(current_members, run_index)
            while primary_id in result["clusters"]:
                primary_id = _stable_new_id(current_members + [primary_id], run_index)

        previous = previous_clusters.get(primary_id)
        if previous and previous.get("state") == "disconfirmed":
            old_id = primary_id
            primary_id = _stable_new_id(current_members, run_index)
            while primary_id in result["clusters"]:
                primary_id = _stable_new_id(current_members + [primary_id], run_index)
            result["clusters"][primary_id] = _new_cluster_record(primary_id, current, run_id, run_index)
            _append_lineage(result, run_id, run_index, "reappeared_after_disconfirmation", source_cluster_id=old_id, cluster_id=primary_id)
        elif previous:
            state = "revived" if previous.get("state") == "decayed" else "active"
            record = dict(previous)
            record.update(
                {
                    "last_seen_run": int(run_index),
                    "last_run_id": str(run_id),
                    "state": state,
                    "missed_runs": 0,
                    "member_ids": current_members,
                    "last_observation": _record_observation(run_id, run_index, primary_id, current, state),
                }
            )
            record.setdefault("observations", []).append(record["last_observation"])
            if state == "revived":
                record["revival_count"] = int(record.get("revival_count", 0)) + 1
                _append_lineage(result, run_id, run_index, "revival", cluster_id=primary_id)
            result["clusters"][primary_id] = record
        else:
            result["clusters"][primary_id] = _new_cluster_record(primary_id, current, run_id, run_index)
            _append_lineage(result, run_id, run_index, "created", cluster_id=primary_id)

        seen_ids.add(primary_id)
        reconciled_cluster = dict(current)
        reconciled_cluster["cluster_id"] = primary_id
        reconciled_cluster["member_ids"] = current_members
        reconciled_cluster["registry_state"] = result["clusters"][primary_id]["state"]
        reconciled.append(reconciled_cluster)

        matched_previous_ids = [candidate[2] for candidate in candidates]
        if primary_id in matched_previous_ids and len(matched_previous_ids) > 1:
            merged_from = sorted(cluster_id for cluster_id in matched_previous_ids if cluster_id != primary_id)
            _append_lineage(result, run_id, run_index, "merge", cluster_id=primary_id, merged_from=merged_from)
        split_children = [
            rc["cluster_id"]
            for rc in reconciled
            if rc["cluster_id"] == primary_id
        ]
        if len(split_children) > 1:
            _append_lineage(result, run_id, run_index, "split", parent_cluster_id=primary_id, child_cluster_ids=sorted(split_children))

        result["signal_history"].append(_record_observation(run_id, run_index, primary_id, current, result["clusters"][primary_id]["state"]))

    for cluster_id, record in list(result["clusters"].items()):
        if cluster_id in seen_ids:
            continue
        if cluster_id in disconfirmed:
            if record.get("state") != "disconfirmed":
                record = dict(record)
                record["state"] = "disconfirmed"
                record["disconfirmation_count"] = int(record.get("disconfirmation_count", 0)) + 1
                record["missed_runs"] = 0
                result["clusters"][cluster_id] = record
                _append_lineage(result, run_id, run_index, "disconfirmation", cluster_id=cluster_id)
            continue
        record = dict(record)
        record["missed_runs"] = int(record.get("missed_runs", 0)) + 1
        if record["missed_runs"] >= cfg["decay_after_missed_runs"] and record.get("state") in ACTIVE_STATES:
            record["state"] = "decayed"
            _append_lineage(result, run_id, run_index, "decay", cluster_id=cluster_id, missed_runs=record["missed_runs"])
        result["clusters"][cluster_id] = record

    # Explicit disconfirmation always wins for this run.
    for cluster_id in sorted(disconfirmed):
        if cluster_id in result["clusters"]:
            record = dict(result["clusters"][cluster_id])
            if record.get("state") != "disconfirmed":
                record["state"] = "disconfirmed"
                record["disconfirmation_count"] = int(record.get("disconfirmation_count", 0)) + 1
                result["clusters"][cluster_id] = record
                _append_lineage(result, run_id, run_index, "disconfirmation", cluster_id=cluster_id)

    result["signal_history"] = sorted(
        result["signal_history"],
        key=lambda observation: (int(observation["run_index"]), str(observation["cluster_id"]), tuple(observation["member_ids"])),
    )
    result["lineage"] = sorted(
        result["lineage"],
        key=lambda event: (int(event["run_index"]), str(event["event"]), _canonical_json(event)),
    )
    return result


def apply_registry_ids(current_clusters: Sequence[Mapping[str, Any]], registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return current clusters annotated with persisted registry state only."""
    clusters = dict(registry.get("clusters") or {})
    output = []
    for cluster in current_clusters:
        item = dict(cluster)
        cluster_id = str(item.get("cluster_id") or "")
        persisted = clusters.get(cluster_id)
        if persisted:
            item["registry_state"] = persisted.get("state", "active")
            item["registry_last_seen_run"] = persisted.get("last_seen_run")
            item["registry_first_seen_run"] = persisted.get("first_seen_run")
        output.append(item)
    return output
