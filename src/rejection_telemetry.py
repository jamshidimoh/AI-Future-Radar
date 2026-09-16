"""Structured, provider-agnostic rejection telemetry.

This module is intentionally passive: recording an event must never alter the
publication decision or raise into the production path.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rejection-event.v1"
SUMMARY_SCHEMA_VERSION = "rejection-summary.v1"


@dataclass(frozen=True)
class RejectionEvent:
    run_id: str
    run_number: int | None
    trace_id: str
    item_id: str
    stage: str
    decision: str
    reason_code: str
    mission_area: str = ""
    content_type: str = ""
    source: str = ""
    source_tier: int | None = None
    global_rank: int | None = None
    normal_rank: int | None = None
    signal_score: float | None = None
    attempt: int | None = None
    replacement_eligible: bool | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["details"] = dict(self.details)
        return value


def build_event(*, run_id: str, trace_id: str, item_id: str, stage: str,
                decision: str, reason_code: str, run_number: int | None = None,
                item: Mapping[str, Any] | None = None, details: Mapping[str, Any] | None = None,
                **kwargs: Any) -> RejectionEvent:
    item = item or {}
    return RejectionEvent(
        run_id=str(run_id),
        run_number=run_number,
        trace_id=str(trace_id),
        item_id=str(item_id),
        stage=str(stage),
        decision=str(decision),
        reason_code=str(reason_code),
        mission_area=str(item.get("mission_area", "") or ""),
        content_type=str(item.get("content_type", "") or ""),
        source=str(item.get("source", "") or ""),
        source_tier=_safe_int(item.get("source_tier")),
        global_rank=_safe_int(item.get("global_rank")),
        normal_rank=_safe_int(item.get("normal_rank")),
        signal_score=_safe_float(item.get("signal_score")),
        attempt=_safe_int(kwargs.get("attempt", item.get("attempt"))),
        replacement_eligible=kwargs.get("replacement_eligible", item.get("replacement_eligible")),
        details=dict(details or {}),
    )


def emit(event: RejectionEvent, path: str | Path) -> None:
    """Append one event and refresh the run summary; telemetry failures are swallowed."""
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        update_summary(event, target)
    except Exception:
        return


def update_summary(event: RejectionEvent, trace_path: str | Path) -> None:
    """Maintain a small incremental summary beside the JSONL trace."""
    try:
        target = Path(trace_path)
        summary_path = target.with_name("rejection_summary.json")
        data = _load_summary(summary_path, event)
        stage = str(event.stage or "unknown")
        reason = str(event.reason_code or "unknown")
        decision = str(event.decision or "unknown")
        data["events"] = int(data.get("events", 0) or 0) + 1
        data.setdefault("by_stage", {}).setdefault(stage, 0)
        data["by_stage"][stage] += 1
        data.setdefault("by_reason", {}).setdefault(reason, 0)
        data["by_reason"][reason] += 1
        data.setdefault("by_decision", {}).setdefault(decision, 0)
        data["by_decision"][decision] += 1
        data["last_event_utc"] = event.timestamp_utc
        data["schema_version"] = SUMMARY_SCHEMA_VERSION
        _write_json(summary_path, data)
    except Exception:
        return


def _load_summary(path: Path, event: RejectionEvent) -> dict[str, Any]:
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("run_id") == event.run_id:
                return loaded
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": event.run_id,
        "run_number": event.run_number,
        "events": 0,
        "by_stage": {},
        "by_reason": {},
        "by_decision": {},
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def _safe_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
