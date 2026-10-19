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


_REMOVED_PROVIDER_FAMILIES = frozenset({
    "gemini",
    "google-genai",
    "google_genai",
    "ollama",
    "ollamalocal",
    "localollama",
    "ollama-local",
    "local-ollama",
})


def prune_removed_provider_health_records(snapshot: Any) -> dict[str, Any]:
    """Discard health records for inference providers removed from the runtime.

    Historical cooldowns must not be merged back into the current state after a
    provider has been deliberately removed. Provider/model keys are normalized
    only for comparison; retained keys and record payloads are left unchanged.
    """
    state = deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    for section in ("models", "providers"):
        records = state.get(section)
        if not isinstance(records, dict):
            continue
        retained = {}
        for key, record in records.items():
            normalized = str(key).strip().casefold()
            family = normalized.split(":", 1)[0] if section == "models" else normalized
            if family not in _REMOVED_PROVIDER_FAMILIES:
                retained[key] = record
        state[section] = retained
    return state


def merge_llm_health_state(remote: Any, local: Any) -> dict[str, Any]:
    """Choose the newest coherent snapshot; ties prefer the current local run.

    Production executions are serialized. Field-wise maxima are incorrect for
    circuit-breaker state because they can revive stale cooldowns cleared by a
    later successful request. Removed provider families are purged before
    choosing either snapshot so stale remote state cannot restore their records.
    """
    remote_state = prune_removed_provider_health_records(remote)
    local_state = prune_removed_provider_health_records(local)
    if not remote_state:
        return deepcopy(local_state)
    if not local_state:
        return deepcopy(remote_state)
    if snapshot_time(remote_state) > snapshot_time(local_state):
        return deepcopy(remote_state)
    return deepcopy(local_state)
