"""G2 persistent trend registry and deterministic lineage reconciliation."""
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
NON_MATCHABLE_STATES = {"disconfirmed", "merged"}


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


def _eligible_previous(current: Mapping[str, Any], previous_clusters: Mapping[str, Any], cfg: Mapping[str, Any]) -> list[tuple[float, int, str]]:
    current_ids = _member_set(current)
    candidates: list[tuple[float, int, str]] = []
    for cluster_id, previous in previous_clusters.items():
        if previous.get("state") in NON_MATCHABLE_STATES:
            continue
        previous_ids = _member_set(previous)
        shared = len(current_ids & previous_ids)
        overlap = member_overlap(current_ids, previous_ids)
        if shared >= cfg["minimum_shared_members"] and overlap >= cfg["identity_overlap_threshold"]:
            candidates.append((overlap, shared, str(cluster_id)))
    return sorted(candidates, key=lambda x: (-x[0], -x[1], x[2]))


def _disconfirmed_matches(current: Mapping[str, Any], previous_clusters: Mapping[str, Any], cfg: Mapping[str, Any]) -> list[tuple[float, int, str]]:
    current_ids = _member_set(current)
    matches: list[tuple[float, int, str]] = []
    for cluster_id, previous in previous_clusters.items():
        if previous.get("state") != "disconfirmed":
            continue
        previous_ids = _member_set(previous)
        shared = len(current_ids & previous_ids)
        overlap = member_overlap(current_ids, previous_ids)
        if shared >= cfg["minimum_shared_members"] and overlap >= cfg["identity_overlap_threshold"]:
            matches.append((overlap, shared, str(cluster_id)))
    return sorted(matches, key=lambda x: (-x[0], -x[1], x[2]))


def _choose_primary(candidates: Sequence[tuple[float, int, str]], previous_clusters: Mapping[str, Any]) -> str:
    ranked = []
    for overlap, shared, cluster_id in candidates:
        previous = previous_clusters[cluster_id]
        ranked.append((overlap, shared, -int(previous.get("first_seen_run", 0) or 0), cluster_id))
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
    observation = _record_observation(run_id, run_index, cluster_id, cluster, "active")
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
        "last_observation": observation,
        "observations": [observation],
    }


def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    if int(registry.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(f"unsupported registry schema_version: {registry.get('schema_version')}")
    if not isinstance(registry.get("clusters"), dict):
        raise ValueError("registry.clusters must be a mapping")
    for key in ("signal_history", "lineage"):
        if not isinstance(registry.get(key), list):
            raise ValueError(f"registry.{key} must be a list")
    return dict(registry)


def load_registry(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return empty_registry()
    return validate_registry(json.loads(target.read_text(encoding="utf-8")))


def save_registry(path: str | Path, registry: Mapping[str, Any]) -> None:
    validate_registry(registry)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(_canonical_json(registry) + "\n", encoding="utf-8")
    temporary.replace(target)


def registry_snapshot(registry: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(_canonical_json(registry))


def reconcile_registry(registry: Mapping[str, Any] | None, current_clusters: Sequence[Mapping[str, Any]], *, run_id: str, run_index: int, config: Mapping[str, Any] | None = None, disconfirmed_ids: Sequence[str] | None = None) -> dict[str, Any]:
    cfg = validate_config(config)
    result = registry_snapshot(registry or empty_registry())
    validate_registry(result)
    if int(run_index) <= int(result.get("last_run_index", 0) or 0):
        raise ValueError("run_index must increase monotonically")

    result["last_run_id"] = str(run_id)
    result["last_run_index"] = int(run_index)
    previous_clusters = dict(result["clusters"])
    disconfirmed = {str(x) for x in (disconfirmed_ids or [])}
    ordered_current = sorted((dict(cluster) for cluster in current_clusters), key=lambda cluster: (sorted(str(x) for x in cluster.get("member_ids", [])), str(cluster.get("cluster_id", ""))))

    candidates_by_index = {index: _eligible_previous(current, previous_clusters, cfg) for index, current in enumerate(ordered_current)}
    parent_to_indices: dict[str, list[int]] = {}
    for index, candidates in candidates_by_index.items():
        if candidates:
            parent = _choose_primary(candidates, previous_clusters)
            parent_to_indices.setdefault(parent, []).append(index)

    keep_parent_index: dict[str, int] = {}
    for parent, indices in parent_to_indices.items():
        keep_parent_index[parent] = max(
            indices,
            key=lambda index: (
                next(candidate[0] for candidate in candidates_by_index[index] if candidate[2] == parent),
                next(candidate[1] for candidate in candidates_by_index[index] if candidate[2] == parent),
                tuple(sorted(_member_set(ordered_current[index]))),
                -index,
            ),
        )

    seen_ids: set[str] = set()
    split_events: set[tuple[str, str]] = set()

    for index, current in enumerate(ordered_current):
        current_members = sorted(str(x) for x in current.get("member_ids", []))
        candidates = candidates_by_index[index]
        parent_id = _choose_primary(candidates, previous_clusters) if candidates else None
        disconfirmed_candidates = _disconfirmed_matches(current, previous_clusters, cfg)

        if disconfirmed_candidates:
            old_id = disconfirmed_candidates[0][2]
            cluster_id = _stable_new_id(current_members, run_index)
            while cluster_id in result["clusters"] or cluster_id in seen_ids:
                cluster_id = _stable_new_id(current_members + [cluster_id], run_index)
            result["clusters"][cluster_id] = _new_cluster_record(cluster_id, current, run_id, run_index)
            _append_lineage(result, run_id, run_index, "reappeared_after_disconfirmation", source_cluster_id=old_id, cluster_id=cluster_id)
        else:
            use_parent = parent_id is not None and keep_parent_index.get(parent_id) == index
            if use_parent:
                cluster_id = parent_id
            else:
                cluster_id = _stable_new_id(current_members, run_index)
                while cluster_id in result["clusters"] or cluster_id in seen_ids:
                    cluster_id = _stable_new_id(current_members + [cluster_id], run_index)
                if parent_id:
                    split_events.add((parent_id, cluster_id))

            previous = previous_clusters.get(cluster_id)
            if previous and previous.get("state") != "disconfirmed":
                state = "revived" if previous.get("state") == "decayed" else "active"
                record = dict(previous)
                observation = _record_observation(run_id, run_index, cluster_id, current, state)
                record.update({"last_seen_run": int(run_index), "last_run_id": str(run_id), "state": state, "missed_runs": 0, "member_ids": current_members, "last_observation": observation, "observations": list(record.get("observations") or []) + [observation]})
                if state == "revived":
                    record["revival_count"] = int(record.get("revival_count", 0)) + 1
                    _append_lineage(result, run_id, run_index, "revival", cluster_id=cluster_id)
                result["clusters"][cluster_id] = record
            else:
                result["clusters"][cluster_id] = _new_cluster_record(cluster_id, current, run_id, run_index)
                _append_lineage(result, run_id, run_index, "created", cluster_id=cluster_id, reason="split_child" if parent_id else "new")

            if parent_id and len(candidates) > 1 and use_parent:
                merged_from = sorted(candidate[2] for candidate in candidates if candidate[2] != parent_id)
                for merged_id in merged_from:
                    merged_record = dict(result["clusters"].get(merged_id, previous_clusters.get(merged_id, {})))
                    if merged_record.get("state") not in NON_MATCHABLE_STATES:
                        merged_record["state"] = "merged"
                        merged_record["merged_into"] = cluster_id
                        merged_record["missed_runs"] = 0
                        result["clusters"][merged_id] = merged_record
                _append_lineage(result, run_id, run_index, "merge", cluster_id=cluster_id, merged_from=merged_from)

        seen_ids.add(cluster_id)
        result["signal_history"].append(_record_observation(run_id, run_index, cluster_id, current, result["clusters"][cluster_id]["state"]))

    for parent_id, child_id in sorted(split_events):
        _append_lineage(result, run_id, run_index, "split", parent_cluster_id=parent_id, child_cluster_id=child_id)

    for cluster_id, record in list(result["clusters"].items()):
        if cluster_id in seen_ids or record.get("state") in NON_MATCHABLE_STATES:
            continue
        updated = dict(record)
        if cluster_id in disconfirmed:
            if updated.get("state") != "disconfirmed":
                updated["state"] = "disconfirmed"
                updated["disconfirmation_count"] = int(updated.get("disconfirmation_count", 0)) + 1
                updated["missed_runs"] = 0
                _append_lineage(result, run_id, run_index, "disconfirmation", cluster_id=cluster_id)
            result["clusters"][cluster_id] = updated
            continue
        updated["missed_runs"] = int(updated.get("missed_runs", 0)) + 1
        if updated["missed_runs"] >= cfg["decay_after_missed_runs"] and updated.get("state") in ACTIVE_STATES:
            updated["state"] = "decayed"
            _append_lineage(result, run_id, run_index, "decay", cluster_id=cluster_id, missed_runs=updated["missed_runs"])
        result["clusters"][cluster_id] = updated

    for cluster_id in sorted(disconfirmed):
        if cluster_id in result["clusters"]:
            record = dict(result["clusters"][cluster_id])
            if record.get("state") != "disconfirmed":
                record["state"] = "disconfirmed"
                record["disconfirmation_count"] = int(record.get("disconfirmation_count", 0)) + 1
                record["missed_runs"] = 0
                _append_lineage(result, run_id, run_index, "disconfirmation", cluster_id=cluster_id)
            result["clusters"][cluster_id] = record

    result["signal_history"] = sorted(result["signal_history"], key=lambda observation: (int(observation["run_index"]), str(observation["cluster_id"]), tuple(observation["member_ids"])))
    result["lineage"] = sorted(result["lineage"], key=lambda event: (int(event["run_index"]), str(event["event"]), _canonical_json(event)))
    return result


def apply_registry_ids(current_clusters: Sequence[Mapping[str, Any]], registry: Mapping[str, Any]) -> list[dict[str, Any]]:
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
