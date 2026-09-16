"""Explicit Mind/Cognition publication policy helpers.

This module is intentionally narrow: it adds a domain-specific publication
floor and minimum coverage guarantee for the mind_cognition mission lane.
It does not relax source, deduplication, grounding, language, or Telegram
safety gates.
"""
from __future__ import annotations

from typing import Any

MIND_COGNITION_SCORE_FLOOR = 50.0
MIND_COGNITION_MIN_PUBLISH = 2
MIND_COGNITION_MAX_PUBLISH = 3


def mission_candidate_score(item: dict[str, Any]) -> float:
    for key in (
        "mind_cognition_original_score",
        "final_editorial_score",
        "radar_composite_score",
        "editorial_score",
        "mission_score",
        "signal_score",
        "score",
    ):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value:
            return value
    return 0.0


def prepare_mind_cognition_contract(items: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    """Set a dynamic mind-lane target: at least two, up to the normal 3-post capacity.

    If three or more mind candidates already clear the 50-point floor, all three
    can be recovered in the mission lane; otherwise two are requested so the top
    two available mind candidates remain publishable even when both are below 50.
    """
    mind = [
        x for x in items
        if str(x.get("mission_area") or "").strip().casefold() == "mind_cognition"
        and not x.get("_publication_blocked")
    ]
    if not mind:
        return
    above_floor = sum(1 for x in mind if _raw_score(x) >= MIND_COGNITION_SCORE_FLOOR)
    desired = min(
        MIND_COGNITION_MAX_PUBLISH,
        max(MIND_COGNITION_MIN_PUBLISH, above_floor),
    )
    contract["mind_cognition_target"] = desired
    contract["mind_cognition_score_floor"] = MIND_COGNITION_SCORE_FLOOR
    contract["mind_cognition_min_publish"] = MIND_COGNITION_MIN_PUBLISH
    contract["mind_cognition_max_publish"] = MIND_COGNITION_MAX_PUBLISH


def _raw_score(item: dict[str, Any]) -> float:
    for key in (
        "mind_cognition_original_score",
        "final_editorial_score",
        "radar_composite_score",
        "editorial_score",
        "mission_score",
        "signal_score",
        "score",
    ):
        try:
            return float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return 0.0


def apply_mind_cognition_floor(item: dict[str, Any]) -> dict[str, Any]:
    """Preserve the real score while making the mind lane pass the legacy 55 gate.

    Scores at or above 50 are accepted as-is. Scores below 50 are only promoted
    for the bounded mind-lane guarantee; the original score is retained in
    ``mind_cognition_original_score`` and the bypass is explicitly marked.
    """
    area = str(item.get("mission_area") or "").strip().casefold()
    if area != "mind_cognition":
        return item

    raw = _raw_score(item)
    item["mind_cognition_original_score"] = raw
    if raw < MIND_COGNITION_SCORE_FLOOR:
        item["mind_cognition_floor_bypass"] = True
        item["mind_cognition_floor"] = MIND_COGNITION_SCORE_FLOOR
        # main.py still carries the historical global 55 gate. Give the special
        # lane an effective score only for that gate while preserving rank order
        # and the actual score for auditability.
        item["final_editorial_score"] = round(55.0 + max(0.0, raw) / 1000.0, 3)
    else:
        item["mind_cognition_floor_bypass"] = False
        item["mind_cognition_floor"] = MIND_COGNITION_SCORE_FLOOR
    return item
