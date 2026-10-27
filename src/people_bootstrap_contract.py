"""Strict, shared validation for the 30-person People Bootstrap ledger."""
from __future__ import annotations

from typing import Any


def people_bootstrap_state_complete(state: Any) -> bool:
    """Validate durable state for 30 unique, delivered people with complete evidence."""
    if not isinstance(state, dict) or str(state.get("status") or "").casefold() != "complete":
        return False
    baseline = state.get("baseline")
    delivered_people = state.get("delivered_people")
    if not isinstance(baseline, dict) or not isinstance(delivered_people, list):
        return False
    delivered = [str(name).strip() for name in delivered_people]
    baseline_names = {str(name).strip() for name in baseline}
    if (
        len(delivered) != 30
        or len(set(delivered)) != 30
        or len(baseline) != 30
        or int(state.get("people_count", 0) or 0) != 30
        or int(state.get("delivered_count", 0) or 0) != 30
        or set(delivered) != baseline_names
    ):
        return False
    for person, row in baseline.items():
        if not str(person).strip() or not isinstance(row, dict):
            return False
        if not all(str(row.get(field) or "").strip() for field in ("title", "link", "published")):
            return False
    return True
