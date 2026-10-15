"""Merge production LLM health snapshots without reviving cleared cooldowns."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


def _epoch(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def snapshot_time(snapshot: dict[str, Any]) -> float:
    """Return the newest timestamp carried by a persisted health snapshot."""
    telemetry = snapshot.get("telemetry")
    timestamps = [snapshot.get("updated_at", 0)]
    if isinstance(telemetry, dict):
        timestamps.append(telemetry.get("updated_at", 0))
    return max((_epoch(value) for value in timestamps), default=0.0)


def merge_llm_health_state(remote: Any, local: Any) -> dict[str, Any]:
    """Choose the newest coherent snapshot; ties prefer the current local run.

    Production executions are serialized. Field-wise maxima are incorrect for
    circuit-breaker state because they can revive stale cooldowns cleared by a
    later successful request.
    """
    remote_state = remote if isinstance(remote, dict) else {}
    local_state = local if isinstance(local, dict) else {}
    if not remote_state:
        return deepcopy(local_state)
    if not local_state:
        return deepcopy(remote_state)
    if snapshot_time(remote_state) > snapshot_time(local_state):
        return deepcopy(remote_state)
    return deepcopy(local_state)
