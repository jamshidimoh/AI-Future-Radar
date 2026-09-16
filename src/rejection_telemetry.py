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
    """Append one event; telemetry failures are swallowed deliberately."""
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


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
