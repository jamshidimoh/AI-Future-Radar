"""Run-scoped, read-only observability for production ranking decisions.

This module never changes ranking inputs or outputs. It records the selected
ranking window so real production runs can be audited and calibrated later.
Artifacts are intentionally ephemeral and uploaded by the production workflow.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "artifacts" / "ranking_audit"
AUDIT_PATH = AUDIT_DIR / "ranking_audit.jsonl"
SUMMARY_PATH = AUDIT_DIR / "ranking_audit_summary.json"


def _num(value):
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _record(item: dict, audit_index: int) -> dict:
    vector = item.get("signal_vector") or {}
    return {
        "schema_version": "ranking-audit.v1",
        "run_id": os.getenv("GITHUB_RUN_ID") or "local",
        "run_number": os.getenv("GITHUB_RUN_NUMBER") or "local",
        "commit_sha": os.getenv("GITHUB_SHA") or "unknown",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "audit_index": audit_index,
        "period_rank": item.get("period_rank"),
        "normal_period_rank": item.get("normal_period_rank"),
        "tier0_rank": item.get("tier0_rank"),
        "title": str(item.get("title") or ""),
        "canonical_url": str(item.get("canonical_url") or item.get("link") or item.get("url") or ""),
        "source": str(item.get("source") or item.get("source_name") or ""),
        "source_type": str(item.get("source_type") or ""),
        "source_tier": item.get("source_tier"),
        "content_type": str(item.get("content_type") or "unknown"),
        "editorial_score": _num(item.get("editorial_score_pre_signal", item.get("editorial_score"))),
        "signal_score": _num(item.get("signal_score")),
        "canonical_rank_score": _num(item.get("final_editorial_score")),
        "signal_class": item.get("signal_class"),
        "signal_vector": {key: _num(vector.get(key)) for key in sorted(vector)},
        "person_tier": bool(item.get("priority_person_interview")),
        "leader": str(item.get("leader") or item.get("watch_person") or ""),
        "protected_content": bool(item.get("protected_content")),
        "protected_reason": str(item.get("protected_reason") or ""),
        "tier0_policy": bool(item.get("_rank_is_tier0")),
        "model_release_priority": bool(item.get("model_release_priority")),
        "legacy_person_bonus": _num(item.get("priority_person_bonus_legacy")),
        "legacy_model_bonus": _num(item.get("model_release_bonus_legacy")),
        "reason_codes": sorted(
            code for code, enabled in {
                "tier0_policy": bool(item.get("_rank_is_tier0")),
                "protected": bool(item.get("protected_content")),
                "model_release": bool(item.get("model_release_priority")),
                "leader_watch": bool(item.get("is_leader_watch") or item.get("leader_watch_protected")),
            }.items() if enabled
        ),
    }


def _display_path(path: Path) -> str:
    """Return a stable repo-relative path, or an absolute test path when needed."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def audit_selection(items: Iterable[dict]) -> Path:
    """Persist a read-only audit record for the ranking window."""
    rows = [_record(item, index) for index, item in enumerate(items, 1)]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "schema_version": "ranking-audit.v1",
        "run_id": os.getenv("GITHUB_RUN_ID") or "local",
        "run_number": os.getenv("GITHUB_RUN_NUMBER") or "local",
        "commit_sha": os.getenv("GITHUB_SHA") or "unknown",
        "record_count": len(rows),
        "max_period_rank": max((row.get("period_rank") or 0 for row in rows), default=0),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "path": _display_path(AUDIT_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[Ranking Audit] records={len(rows)} path={AUDIT_PATH}", flush=True)
    return AUDIT_PATH
