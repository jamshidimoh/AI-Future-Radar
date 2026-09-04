#!/usr/bin/env python3
"""Validate the human-annotated historical gold dataset.

The validator deliberately fails closed: a seed with missing judgments is not
accepted as a gold dataset.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    "canonical_story_id",
    "should_publish",
    "importance_band",
    "relevance_band",
    "best_source",
    "expected_story_group",
    "is_duplicate",
    "leader_relevance",
    "is_substantive_interview",
    "is_model_release",
    "risk_level",
    "minimum_evidence_level",
    "expected_rank_band",
    "expected_content_type",
    "notes",
}

ENUMS = {
    "importance_band": {"high", "medium", "low"},
    "relevance_band": {"high", "medium", "low"},
    "leader_relevance": {"high", "medium", "low", "none"},
    "risk_level": {"low", "medium", "high", "critical"},
    "minimum_evidence_level": {
        "OBSERVED", "SUPPORTED", "CORROBORATED", "INFERRED", "HYPOTHESIS"
    },
    "expected_rank_band": {"top", "middle", "bottom"},
}
BOOLEANS = {"should_publish", "is_duplicate", "is_substantive_interview", "is_model_release"}


def fail(message: str) -> int:
    print(f"GOLDEN_DATASET_VALIDATION=FAIL {message}")
    return 1


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/golden_dataset.jsonl")
    if not path.exists():
        return fail("BLOCKED_NO_GOLD_LABELS")

    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            return fail(f"invalid_json line={line_no} error={exc}")
        if not isinstance(record, dict):
            return fail(f"record_not_object line={line_no}")
        records.append(record)

    if not records:
        return fail("EMPTY")

    for idx, record in enumerate(records, 1):
        missing = sorted(REQUIRED - record.keys())
        if missing:
            return fail(f"record={idx} missing={','.join(missing)}")
        for field in BOOLEANS:
            if not isinstance(record[field], bool):
                return fail(f"record={idx} field={field} expected_boolean")
        for field, allowed in ENUMS.items():
            if record[field] not in allowed:
                return fail(f"record={idx} field={field} invalid={record[field]!r}")
        for field in ("canonical_story_id", "expected_story_group", "notes"):
            if not isinstance(record[field], str) or not record[field].strip():
                return fail(f"record={idx} field={field} empty")

    groups = {r["expected_story_group"] for r in records}
    print(f"GOLDEN_DATASET records={len(records)} story_groups={len(groups)}")
    print("GOLDEN_DATASET_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
