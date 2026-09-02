import json

import pytest

from src.trend_registry_v2 import (
    empty_registry,
    load_registry,
    member_overlap,
    reconcile_registry,
    registry_snapshot,
    save_registry,
    validate_config,
)


def cluster(*member_ids, score=70.0):
    return {
        "member_ids": list(member_ids),
        "trend_score": score,
        "trend_confidence": 0.75,
    }


def test_new_cluster_gets_stable_persistent_identity():
    first = reconcile_registry(empty_registry(), [cluster("a", "b")], run_id="r1", run_index=1)
    cluster_id = next(iter(first["clusters"]))
    second = reconcile_registry(first, [cluster("a", "b")], run_id="r2", run_index=2)
    assert next(iter(second["clusters"])) == cluster_id
    assert second["clusters"][cluster_id]["last_seen_run"] == 2


def test_restart_round_trip_preserves_registry_identity(tmp_path):
    path = tmp_path / "trend_registry.json"
    first = reconcile_registry(empty_registry(), [cluster("a", "b")], run_id="r1", run_index=1)
    save_registry(path, first)
    restored = load_registry(path)
    second = reconcile_registry(restored, [cluster("a", "b", "c")], run_id="r2", run_index=2)
    assert len(second["clusters"]) == 1
    assert next(iter(second["clusters"])) == next(iter(first["clusters"]))
    assert len(second["signal_history"]) == 2


def test_replayed_signal_cluster_does_not_create_false_new_cluster():
    first = reconcile_registry(empty_registry(), [cluster("a", "b")], run_id="r1", run_index=1)
    cluster_id = next(iter(first["clusters"]))
    replayed = reconcile_registry(
        first,
        [cluster("b", "a"), cluster("a", "b")],
        run_id="r2",
        run_index=2,
    )
    assert len(replayed["clusters"]) == 1
    assert cluster_id in replayed["clusters"]
    assert len(replayed["signal_history"]) == 2
    assert replayed["signal_history"][-1]["cluster_id"] == cluster_id


def test_merge_keeps_strongest_previous_identity_and_records_lineage():
    first = reconcile_registry(
        empty_registry(),
        [cluster("a", "b"), cluster("c", "d")],
        run_id="r1",
        run_index=1,
    )
    ids = sorted(first["clusters"])
    merged = reconcile_registry(
        first,
        [cluster("a", "b", "c", "d")],
        run_id="r2",
        run_index=2,
    )
    kept = ids[0]
    assert merged["clusters"][kept]["last_seen_run"] == 2
    merge_events = [event for event in merged["lineage"] if event["event"] == "merge"]
    assert merge_events
    assert merge_events[-1]["cluster_id"] == kept
    assert ids[1] in merge_events[-1]["merged_from"]


def test_split_keeps_parent_for_best_child_and_creates_child_lineage():
    first = reconcile_registry(empty_registry(), [cluster("a", "b", "c", "d")], run_id="r1", run_index=1)
    parent = next(iter(first["clusters"]))
    split = reconcile_registry(
        first,
        [cluster("a", "b"), cluster("c", "d")],
        run_id="r2",
        run_index=2,
    )
    assert len(split["clusters"]) == 2
    assert parent in split["clusters"]
    split_events = [event for event in split["lineage"] if event["event"] == "split"]
    assert split_events
    assert split_events[-1]["parent_cluster_id"] == parent
    child = split_events[-1]["child_cluster_id"]
    assert child != parent
    assert child in split["clusters"]


def test_decay_and_revival_preserve_identity():
    first = reconcile_registry(empty_registry(), [cluster("a", "b")], run_id="r1", run_index=1)
    cluster_id = next(iter(first["clusters"]))
    decayed = reconcile_registry(first, [], run_id="r2", run_index=2)
    assert decayed["clusters"][cluster_id]["state"] == "decayed"
    revived = reconcile_registry(decayed, [cluster("a", "b")], run_id="r3", run_index=3)
    assert revived["clusters"][cluster_id]["state"] == "revived"
    assert revived["clusters"][cluster_id]["revival_count"] == 1
    assert any(event["event"] == "decay" for event in revived["lineage"])
    assert any(event["event"] == "revival" for event in revived["lineage"])


def test_disconfirmation_is_terminal_and_reappearance_gets_new_identity():
    first = reconcile_registry(empty_registry(), [cluster("a", "b")], run_id="r1", run_index=1)
    old_id = next(iter(first["clusters"]))
    disconfirmed = reconcile_registry(
        first,
        [],
        run_id="r2",
        run_index=2,
        disconfirmed_ids=[old_id],
    )
    assert disconfirmed["clusters"][old_id]["state"] == "disconfirmed"
    reappeared = reconcile_registry(disconfirmed, [cluster("a", "b")], run_id="r3", run_index=3)
    assert len(reappeared["clusters"]) == 2
    assert old_id in reappeared["clusters"]
    new_ids = [cluster_id for cluster_id in reappeared["clusters"] if cluster_id != old_id]
    assert len(new_ids) == 1
    assert any(
        event["event"] == "reappeared_after_disconfirmation"
        and event["source_cluster_id"] == old_id
        for event in reappeared["lineage"]
    )


def test_lineage_and_history_are_deterministically_reconstructable():
    runs = [
        [cluster("a", "b"), cluster("c", "d")],
        [cluster("a", "b", "c", "d")],
        [],
        [cluster("a", "b", "c", "d")],
    ]
    registry = empty_registry()
    for index, current in enumerate(runs, 1):
        registry = reconcile_registry(registry, current, run_id=f"r{index}", run_index=index)
    snapshot_a = registry_snapshot(registry)
    snapshot_b = registry_snapshot(registry)
    assert snapshot_a == snapshot_b
    assert registry["last_run_index"] == 4
    assert [event["event"] for event in registry["lineage"]].count("merge") == 1
    assert [event["event"] for event in registry["lineage"]].count("decay") == 1
    assert [event["event"] for event in registry["lineage"]].count("revival") == 1


def test_save_registry_writes_valid_json_and_validate_config_fails_closed(tmp_path):
    registry = empty_registry()
    path = tmp_path / "registry.json"
    save_registry(path, registry)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2
    with pytest.raises(ValueError):
        validate_config({"identity_overlap_threshold": 0.0})
    assert member_overlap(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
