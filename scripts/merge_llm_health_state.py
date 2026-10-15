"""Reconcile LLM health snapshots without resurrecting recovered failures.

The production workflow serializes bot runs. Each local health snapshot starts
from the checked-out state and records successes/failures observed by that run.
The latest run snapshot is authoritative for models/providers; unioning old
entries with the remote snapshot can resurrect cooldowns cleared by success.
"""
from __future__ import annotations

from typing import Any


def _normalize_section(section: Any) -> dict[str, dict[str, Any]]:
    """Normalize legacy case-variant keys within one snapshot only."""
    normalized: dict[str, dict[str, Any]] = {}
    if not isinstance(section, dict):
        return normalized

    for raw_key, raw_value in section.items():
        if not isinstance(raw_value, dict):
            continue
        key = str(raw_key).strip().casefold()
        if not key:
            continue
        value = dict(raw_value)
        current = normalized.get(key)
        if current is None:
            normalized[key] = value
            continue

        # Case-variant aliases may coexist in legacy snapshots. Conservatively
        # merge duplicate aliases here, but never across distinct run snapshots.
        try:
            current["failures"] = max(
                int(current.get("failures", 0) or 0),
                int(value.get("failures", 0) or 0),
            )
        except (TypeError, ValueError):
            pass
        for field in ("disabled_until", "last_success"):
            try:
                current[field] = max(
                    float(current.get(field, 0) or 0),
                    float(value.get(field, 0) or 0),
                )
            except (TypeError, ValueError):
                pass
        if not current.get("last_error") and value.get("last_error"):
            current["last_error"] = value["last_error"]

    return normalized


def merge_health_state(remote: Any, local: Any) -> dict[str, Any]:
    """Use the current run snapshot for model/provider health and telemetry."""
    remote_state = remote if isinstance(remote, dict) else {}
    local_state = local if isinstance(local, dict) else {}
    merged = dict(remote_state)
    merged.update(local_state)

    # Empty local sections are meaningful: they indicate that the current
    # runtime cleared stale entries after a successful provider/model probe.
    for section in ("models", "providers"):
        merged[section] = _normalize_section(local_state.get(section))

    # Telemetry is per-run evidence, not a cumulative high-water mark.
    for key in ("telemetry", "updated_at", "observed_failures", "observed_events"):
        if key in local_state:
            merged[key] = local_state[key]

    return merged
