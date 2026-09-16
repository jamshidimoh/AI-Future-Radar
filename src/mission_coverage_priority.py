"""Deterministic historical mission-lane priority for recovery candidates."""
from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from typing import Any

from src.mind_cognition_lane import apply_mind_cognition_floor, prepare_mind_cognition_contract
from src.unified_editorial_selection import mission_area

_TARGET_KEYS = {
    "ai_core": "ai_core_target_min",
    "convergence": "convergence_target",
    "mind_cognition": "mind_cognition_target",
    "future_governance": "mind_future_target",
}


def _score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "radar_composite_score", "editorial_score", "mission_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value:
            return value
    return 0.0


def _tier(item: dict[str, Any]) -> int | None:
    try:
        value = item.get("source_tier", item.get("tier"))
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def historical_area_counts(history: Iterable[dict[str, Any]], window_items: int) -> dict[str, int]:
    recent = [x for x in history or [] if str(x.get("content_type") or "").strip().casefold() != "education"]
    recent = recent[-max(0, int(window_items or 0)):] if window_items else []
    counts: dict[str, int] = {}
    for record in recent:
        area = mission_area(record)
        counts[area] = counts.get(area, 0) + 1
    return counts


def mission_coverage_bonus(item: dict[str, Any], area_counts: dict[str, int], contract: dict[str, Any]) -> float:
    area = mission_area(item)
    target_key = _TARGET_KEYS.get(area)
    if not target_key or int(contract.get(target_key, 0) or 0) <= 0:
        return 0.0
    count = int(area_counts.get(area, 0) or 0)
    if count >= 2:
        return 0.0

    raw_score = float(item.get("mind_cognition_original_score", _score(item)) or 0.0)
    if area == "mind_cognition":
        # The new Mind/Cognition floor is 50. The existing global runtime gate
        # remains 55, so a bounded additive bonus closes the gap for all valid
        # mind candidates at or above 50 without changing other mission lanes.
        if raw_score >= 50.0 and _tier(item) in {1, 2}:
            legacy_bonus = 1.5 if count == 0 else 1.0
            return max(legacy_bonus, max(0.0, 55.0 - raw_score))
        # Candidates below 50 are handled by the explicit top-two bypass marker
        # in apply_mind_cognition_floor; they do not receive a ranking bonus.
        return 0.0

    if _score(item) < 52.0:
        return 0.0
    if _tier(item) not in {1, 2}:
        return 0.0
    return 1.5 if count == 0 else 1.0


def annotate_recovery_candidates(items: Iterable[dict[str, Any]], history: Iterable[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    source_items = [dict(raw) for raw in items or []]
    for item in source_items:
        if mission_area(item) == "mind_cognition":
            apply_mind_cognition_floor(item)
    prepare_mind_cognition_contract(source_items, contract)

    window_items = int(contract.get("window_runs", 6) or 6) * max(1, int(contract.get("max_posts", 3) or 3))
    counts = historical_area_counts(history, window_items)
    prepared: list[dict[str, Any]] = []
    for item in source_items:
        area = mission_area(item)
        original_score = float(item.get("mind_cognition_original_score", _score(item)) or 0.0)
        bonus = mission_coverage_bonus(item, counts, contract)
        item["historical_mission_area_count"] = int(counts.get(area, 0) or 0)
        item["mission_coverage_bonus"] = bonus
        if bonus > 0:
            with suppress(TypeError, ValueError):
                item["final_editorial_score"] = round(_score(item) + bonus, 2)
        if area == "mind_cognition":
            item["mind_cognition_original_score"] = original_score
        prepared.append(item)
    prepared.sort(
        key=lambda x: (
            1 if mission_area(x) == "mind_cognition" else 0,
            float(x.get("mind_cognition_original_score", _score(x)) or 0),
            float(x.get("mission_coverage_bonus", 0) or 0),
            str(x.get("published", "")),
        ),
        reverse=True,
    )
    return prepared
