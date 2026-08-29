"""Unified, deterministic editorial portfolio selection contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
MISSION_PATH = ROOT / "config" / "mission_policy.yaml"
SELECTION_PATH = ROOT / "config" / "selection_policy.yaml"

_AREA_MAP = {
    "ai": "ai_core",
    "ai_core": "ai_core",
    "quantum": "convergence",
    "genetics": "convergence",
    "robotics": "convergence",
    "humanoid": "convergence",
    "bio": "convergence",
    "bci": "convergence",
    "future": "future_governance",
    "future_governance": "future_governance",
    "mind": "mind_cognition",
    "mind_cognition": "mind_cognition",
    "convergence": "convergence",
}

_RESEARCH_TYPES = {"research", "paper", "study", "preprint"}
_COMMUNITY_MARKERS = ("reddit", "community", "aggregator")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_editorial_contract(selection: dict[str, Any] | None = None) -> dict[str, Any]:
    mission = _load_yaml(MISSION_PATH).get("mission", {})
    selection_cfg = selection or _load_yaml(SELECTION_PATH).get("selection", {})
    return {
        "max_posts": int(selection_cfg.get("max_posts", 4) or 4),
        "candidate_window": int(selection_cfg.get("candidate_window", 6) or 6),
        "replacement_buffer": int(selection_cfg.get("replacement_buffer", 2) or 2),
        "max_items_per_source": int(selection_cfg.get("max_items_per_source", 2) or 2),
        "max_items_per_content_type": int(selection_cfg.get("max_items_per_content_type", 2) or 2),
        "preferred_max_same_source": int(mission.get("max_same_source", 1) or 1),
        "hard_max_same_source": int(selection_cfg.get("max_items_per_source", 2) or 2),
        "min_unique_sources": int(mission.get("min_unique_sources", 3) or 3),
        "min_authoritative_items": int(mission.get("min_authoritative_items", 2) or 2),
        "community_max": int(mission.get("community_max", 0) or 0),
        "max_same_mission_area": int(mission.get("max_same_mission_area", 2) or 2),
        "required_areas": ("ai_core", "convergence", "mind_cognition", "future_governance"),
    }


def source_key(item: dict[str, Any]) -> str:
    return str(item.get("source") or item.get("source_name") or item.get("source_domain") or "unknown").strip().casefold() or "unknown"


def content_type_key(item: dict[str, Any]) -> str:
    return str(item.get("content_type") or "unknown").strip().casefold() or "unknown"


def mission_area(item: dict[str, Any]) -> str:
    explicit = str(item.get("mission_area") or "").strip().casefold()
    if explicit in _AREA_MAP.values():
        return explicit
    category = str(item.get("category") or "").strip().casefold()
    if category in _AREA_MAP:
        return _AREA_MAP[category]
    if item.get("research_signal") or content_type_key(item) in _RESEARCH_TYPES:
        return "ai_core"
    return "ai_core"


def _source_tier(item: dict[str, Any]) -> int | None:
    raw = item.get("source_tier", item.get("tier"))
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _is_community(item: dict[str, Any]) -> bool:
    value = " ".join(
        str(item.get(key) or "").strip().casefold()
        for key in ("source", "source_name", "source_type", "source_domain")
    )
    if any(marker in value for marker in _COMMUNITY_MARKERS):
        return True
    tier = _source_tier(item)
    return tier is not None and tier >= 3


def candidate_score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "editorial_score", "mission_score", "signal_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value:
            return value
    return 0.0


def _rank_key(item: dict[str, Any], recent_source_counts: dict[str, int]) -> tuple:
    source = source_key(item)
    recent_penalty = min(3, max(0, int(recent_source_counts.get(source, 0) or 0))) * 2.0
    effective_score = candidate_score(item) - recent_penalty
    return (
        -effective_score,
        -float(item.get("signal_score", 0) or 0),
        -float(item.get("mission_score", 0) or 0),
        recent_source_counts.get(source, 0),
        str(item.get("published", "")),
    )


def select_regular_portfolio(
    candidates: Iterable[dict[str, Any]],
    *,
    max_posts: int,
    max_per_source: int,
    max_per_type: int,
    recent_source_counts: dict[str, int] | None = None,
    contract: dict[str, Any] | None = None,
    mission_aware: bool = True,
) -> list[dict[str, Any]]:
    """Select a deterministic portfolio; optionally apply mission coverage before score fill."""
    contract = contract or load_editorial_contract()
    limit = max(0, int(max_posts or 0))
    source_cap = max(1, int(max_per_source or contract["hard_max_same_source"]))
    type_cap = max(1, int(max_per_type or 1))
    recent = recent_source_counts or {}

    eligible = []
    for raw in candidates or []:
        item = dict(raw)
        if _is_community(item) and contract["community_max"] <= 0:
            continue
        item["mission_area"] = mission_area(item)
        eligible.append(item)
    ordered = sorted(eligible, key=lambda x: _rank_key(x, recent))

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    source_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}

    def admissible(item: dict[str, Any], *, repeat_source: bool) -> bool:
        source = source_key(item)
        ctype = content_type_key(item)
        if type_counts.get(ctype, 0) >= type_cap:
            return False
        current_source = source_counts.get(source, 0)
        if repeat_source:
            if current_source >= source_cap:
                return False
        elif current_source:
            return False
        return True

    def add(item: dict[str, Any], reason: str) -> None:
        source, ctype = source_key(item), content_type_key(item)
        selected.append(item)
        selected_ids.add(id(item))
        source_counts[source] = source_counts.get(source, 0) + 1
        type_counts[ctype] = type_counts.get(ctype, 0) + 1
        item["mission_selection_reason"] = reason

    if mission_aware:
        for area in ("convergence", "mind_cognition", "future_governance"):
            if len(selected) >= limit:
                break
            pool = [x for x in ordered if mission_area(x) == area and admissible(x, repeat_source=False)]
            if pool:
                add(pool[0], f"mission_coverage:{area}")

        if len(selected) < limit:
            research_pool = [
                x for x in ordered
                if (content_type_key(x) in _RESEARCH_TYPES or x.get("research_signal"))
                and admissible(x, repeat_source=False)
            ]
            if research_pool:
                add(research_pool[0], "research_evidence")

    for item in ordered:
        if len(selected) >= limit:
            break
        if id(item) in selected_ids:
            continue
        if admissible(item, repeat_source=False):
            add(item, "distinct_source_fill")

    if len(selected) < limit and source_cap > 1:
        for item in ordered:
            if len(selected) >= limit:
                break
            if id(item) in selected_ids:
                continue
            if admissible(item, repeat_source=True):
                add(item, "adaptive_source_backfill")

    return selected[:limit]


def assert_portfolio_contract(selected: Iterable[dict[str, Any]], *, contract: dict[str, Any] | None = None) -> None:
    contract = contract or load_editorial_contract()
    items = list(selected or [])
    source_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    for item in items:
        source_counts[source_key(item)] = source_counts.get(source_key(item), 0) + 1
        area = mission_area(item)
        area_counts[area] = area_counts.get(area, 0) + 1
    assert max(source_counts.values(), default=0) <= contract["hard_max_same_source"]
    assert max(area_counts.values(), default=0) <= contract["max_same_mission_area"]
    if len(items) >= contract["min_unique_sources"]:
        assert len(source_counts) >= contract["min_unique_sources"]
    assert sum(1 for item in items if not _is_community(item)) == len(items)


__all__ = [
    "assert_portfolio_contract",
    "candidate_score",
    "content_type_key",
    "load_editorial_contract",
    "mission_area",
    "select_regular_portfolio",
    "source_key",
]
