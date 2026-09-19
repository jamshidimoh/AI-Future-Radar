"""Compatibility helpers for the legacy mind_cognition mission contract.

The production Mind/Ideas/Voices lane is independent from the normal-news
score floor. These helpers remain only for older mission-recovery contracts and
tests; they preserve the original score and explicit bypass metadata without
changing the first-class Mind lane semantics.
"""
from __future__ import annotations

from typing import Any

MIND_COGNITION_SCORE_FLOOR = 50.0
MIND_COGNITION_MIN_PUBLISH = 1
MIND_COGNITION_MAX_PUBLISH = 2


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


def _is_mind_cognition(item: dict[str, Any]) -> bool:
    area = str(item.get("mission_area") or "").strip().casefold()
    category = str(item.get("category") or "").strip().casefold()
    return area == "mind_cognition" or category == "mind"


def prepare_mind_cognition_contract(items: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    """Preserve the explicit mission target; expose only legacy compatibility metadata."""
    mind = [x for x in items if _is_mind_cognition(x) and not x.get("_publication_blocked")]
    if not mind:
        return

    # The authoritative mission target comes from mission_policy.yaml via
    # load_editorial_contract(). This compatibility helper must never silently
    # raise that target just because Mind candidates are present. The additive
    # Mind/Ideas/Voices publication lane has its own cap and is not a reason to
    # mutate the normal mission-coverage target.
    configured_target = contract.get("mind_cognition_target", MIND_COGNITION_MIN_PUBLISH)
    try:
        target = max(0, int(configured_target))
    except (TypeError, ValueError):
        target = MIND_COGNITION_MIN_PUBLISH
    contract["mind_cognition_target"] = target
    contract["mind_cognition_score_floor"] = MIND_COGNITION_SCORE_FLOOR
    contract["mind_cognition_min_publish"] = min(MIND_COGNITION_MIN_PUBLISH, target) if target else 0
    contract["mind_cognition_max_publish"] = MIND_COGNITION_MAX_PUBLISH


def _raw_score(item: dict[str, Any]) -> float:
    """Read the pre-floor score from the most authoritative explicit score field."""
    preferred_keys = (
        "final_editorial_score",
        "radar_composite_score",
        "editorial_score",
        "mission_score",
        "signal_score",
        "score",
        "mind_cognition_original_score",
    )
    for key in preferred_keys:
        if key not in item:
            continue
        value = item.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    try:
        return float(item.get("mind_cognition_original_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def apply_mind_cognition_floor(item: dict[str, Any]) -> dict[str, Any]:
    """Preserve the raw Mind score while exposing legacy bypass metadata.

    The historical tests expect a bounded effective score for old callers. The
    first-class Mind publication lane does not rely on this effective score.
    """
    if not _is_mind_cognition(item):
        return item

    raw = _raw_score(item)
    item["mind_cognition_original_score"] = raw
    item["mind_cognition_floor"] = MIND_COGNITION_SCORE_FLOOR
    item["mind_cognition_floor_bypass"] = raw < MIND_COGNITION_SCORE_FLOOR
    if raw < MIND_COGNITION_SCORE_FLOOR:
        item["final_editorial_score"] = round(55.0 + max(0.0, raw) / 1000.0, 3)
    return item
