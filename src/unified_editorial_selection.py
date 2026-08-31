"""Unified, deterministic editorial portfolio selection contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
MISSION_PATH = ROOT / "config" / "mission_policy.yaml"
SELECTION_PATH = ROOT / "config" / "selection_policy.yaml"

_AREA_MAP = {"ai": "ai_core", "ai_core": "ai_core", "quantum": "convergence", "genetics": "convergence", "robotics": "convergence", "humanoid": "convergence", "bio": "convergence", "bci": "convergence", "future": "future_governance", "future_governance": "future_governance", "mind": "mind_cognition", "mind_cognition": "mind_cognition", "convergence": "convergence"}
_RESEARCH_TYPES = {"research", "paper", "study", "preprint"}
_INTERVIEW_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a"}
_COMMUNITY_MARKERS = ("reddit", "community", "aggregator")
_GENERIC_AI_TERMS = {"model", "agent", "reasoning", "ai", "artificial intelligence"}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_editorial_contract(selection: dict[str, Any] | None = None) -> dict[str, Any]:
    mission = _load_yaml(MISSION_PATH).get("mission", {})
    selection_cfg = selection or _load_yaml(SELECTION_PATH).get("selection", {})
    return {
        "max_posts": int(selection_cfg.get("max_posts", mission.get("operational_publication_capacity", 4)) or 4),
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
        "ai_core_target_min": int(mission.get("ai_core_target_min", 1) or 0),
        "ai_core_target_max": int(mission.get("ai_core_target_max", 2) or 99),
        "convergence_target": int(mission.get("convergence_target", 1) or 0),
        "mind_future_target": int(mission.get("mind_future_target", 1) or 0),
        "research_target": int(mission.get("research_target", 1) or 0),
        "interview_target_max": int(mission.get("interview_target_max", 1) or 0),
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


def _mission_text(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k) or "") for k in ("title", "summary", "description", "category", "mission_area", "content_type", "tags", "keywords")).casefold()


def _keyword_match_area(item: dict[str, Any]) -> str | None:
    text = _mission_text(item)
    matches: list[tuple[int, str]] = []
    for area, cfg in _load_yaml(MISSION_PATH).get("areas", {}).items():
        for keyword in cfg.get("keywords", []) or []:
            key = str(keyword).strip().casefold()
            if not key or key not in text:
                continue
            if area == "ai_core" and key in _GENERIC_AI_TERMS:
                continue
            matches.append((len(key), area))
    return max(matches, key=lambda x: x[0])[1] if matches else None


def is_mission_relevant(item: dict[str, Any], *, strict: bool = True) -> bool:
    explicit = str(item.get("mission_area") or "").strip().casefold()
    if explicit in _AREA_MAP.values():
        return True
    category = str(item.get("category") or "").strip().casefold()
    if category in _AREA_MAP:
        item["mission_area"] = _AREA_MAP[category]
        return True
    matched_area = _keyword_match_area(item)
    if matched_area:
        item["mission_area"] = matched_area
        return True
    if not strict:
        return True
    return item.get("_ai_link") is True or item.get("ai_relevance") is True


def _source_tier(item: dict[str, Any]) -> int | None:
    raw = item.get("source_tier", item.get("tier"))
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _is_community(item: dict[str, Any]) -> bool:
    value = " ".join(str(item.get(k) or "").strip().casefold() for k in ("source", "source_name", "source_type", "source_domain"))
    if any(m in value for m in _COMMUNITY_MARKERS):
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


def _safe_float(item: dict[str, Any], key: str) -> float:
    try:
        return float(item.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _rank_key(item: dict[str, Any], recent_source_counts: dict[str, int]) -> tuple:
    source = source_key(item)
    recent_penalty = min(3, max(0, int(recent_source_counts.get(source, 0) or 0))) * 2.0
    effective_score = candidate_score(item) - recent_penalty
    confidence = max(0.0, min(1.0, _safe_float(item, "ai_relevance_confidence")))
    evidence_strength = _safe_float(item, "evidence_strength")
    source_tier = _source_tier(item)
    authority = 0 if source_tier is None else max(0, 4 - source_tier)
    return (-effective_score, -confidence, -evidence_strength, -authority, -_safe_float(item, "signal_score"), -_safe_float(item, "mission_score"), recent_source_counts.get(source, 0), str(item.get("published", "")))


def _is_research(item: dict[str, Any]) -> bool:
    return content_type_key(item) in _RESEARCH_TYPES or bool(item.get("research_signal"))


def _is_interview(item: dict[str, Any]) -> bool:
    return content_type_key(item) in _INTERVIEW_TYPES or bool(item.get("interview_signal"))


def _authority_ok(item: dict[str, Any]) -> bool:
    return _source_tier(item) in {1, 2}


def select_regular_portfolio(candidates: Iterable[dict[str, Any]], *, max_posts: int, max_per_source: int, max_per_type: int, recent_source_counts: dict[str, int] | None = None, contract: dict[str, Any] | None = None, mission_aware: bool = True, strict_relevance: bool = False) -> list[dict[str, Any]]:
    contract = contract or load_editorial_contract()
    limit = max(0, int(max_posts or 0))
    source_cap = max(1, int(max_per_source or contract["hard_max_same_source"]))
    type_cap = max(1, int(max_per_type or 1))
    recent = recent_source_counts or {}
    eligible: list[dict[str, Any]] = []
    for raw in list(candidates or []):
        item = dict(raw)
        if _is_community(item) and contract["community_max"] <= 0:
            continue
        if not is_mission_relevant(item, strict=strict_relevance):
            continue
        item["mission_area"] = mission_area(item)
        eligible.append(item)
    ordered = sorted(eligible, key=lambda x: _rank_key(x, recent))
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    source_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    interview_count = 0

    def admissible(item: dict[str, Any], *, repeat_source: bool) -> bool:
        source, ctype, area = source_key(item), content_type_key(item), mission_area(item)
        if type_counts.get(ctype, 0) >= type_cap:
            return False
        if mission_aware and _is_interview(item) and interview_count >= contract["interview_target_max"] > 0:
            return False
        if mission_aware and area_counts.get(area, 0) >= contract["max_same_mission_area"]:
            return False
        current_source = source_counts.get(source, 0)
        return current_source < source_cap if repeat_source else current_source == 0

    def add(item: dict[str, Any], reason: str) -> None:
        nonlocal interview_count
        source, ctype, area = source_key(item), content_type_key(item), mission_area(item)
        selected.append(item)
        selected_ids.add(id(item))
        source_counts[source] = source_counts.get(source, 0) + 1
        type_counts[ctype] = type_counts.get(ctype, 0) + 1
        if mission_aware:
            area_counts[area] = area_counts.get(area, 0) + 1
        if _is_interview(item):
            interview_count += 1
        item["mission_selection_reason"] = reason

    def remove(item: dict[str, Any]) -> None:
        nonlocal interview_count
        selected.remove(item)
        selected_ids.remove(id(item))
        source_counts[source_key(item)] -= 1
        type_counts[content_type_key(item)] -= 1
        if mission_aware:
            area_counts[mission_area(item)] -= 1
        if _is_interview(item):
            interview_count -= 1

    def best(pool: list[dict[str, Any]], *, prefer_research: bool = False) -> dict[str, Any] | None:
        candidates2 = [x for x in pool if admissible(x, repeat_source=False)]
        if not candidates2:
            return None
        if prefer_research:
            research_first = [x for x in candidates2 if _is_research(x)]
            if research_first:
                candidates2 = research_first
        return max(candidates2, key=lambda x: (-_rank_key(x, recent)[0], candidate_score(x)))

    if mission_aware and limit > 0:
        for _ in range(min(contract["ai_core_target_min"], limit)):
            c = best([x for x in ordered if mission_area(x) == "ai_core"], prefer_research=True)
            if c is None:
                break
            add(c, "mission_target:ai_core")
        for _ in range(min(contract["convergence_target"], max(0, limit - len(selected)))):
            c = best([x for x in ordered if mission_area(x) == "convergence"], prefer_research=True)
            if c is None:
                break
            add(c, "mission_target:convergence")
        for _ in range(min(contract["mind_future_target"], max(0, limit - len(selected)))):
            c = best([x for x in ordered if mission_area(x) in {"mind_cognition", "future_governance"}], prefer_research=True)
            if c is None:
                break
            add(c, f"mission_target:{mission_area(c)}")
        for _ in range(min(contract["research_target"], max(0, limit - len(selected)))):
            c = best([x for x in ordered if _is_research(x)], prefer_research=True)
            if c is None:
                break
            add(c, "mission_target:research")

    for item in ordered:
        if len(selected) >= limit or id(item) in selected_ids:
            break
        if admissible(item, repeat_source=False):
            if mission_aware and mission_area(item) == "ai_core" and area_counts.get("ai_core", 0) >= contract["ai_core_target_max"]:
                continue
            add(item, "score_fill")

    # Two-phase diversity: fill every distinct source first, then use repeats up to the hard source cap.
    if len(selected) < limit and source_cap > 1:
        for item in ordered:
            if len(selected) >= limit:
                break
            if id(item) in selected_ids:
                continue
            source, ctype, area = source_key(item), content_type_key(item), mission_area(item)
            if type_counts.get(ctype, 0) >= type_cap:
                continue
            if mission_aware:
                if area_counts.get(area, 0) >= contract["max_same_mission_area"]:
                    continue
                if _is_interview(item) and interview_count >= contract["interview_target_max"] > 0:
                    continue
            if source_counts.get(source, 0) < source_cap:
                add(item, "adaptive_source_backfill")

    auth_required = min(contract["min_authoritative_items"], len(selected))
    while mission_aware and sum(_authority_ok(x) for x in selected) < auth_required:
        replacement = next((x for x in ordered if id(x) not in selected_ids and _authority_ok(x) and admissible(x, repeat_source=False)), None)
        removable = [x for x in selected if not _authority_ok(x)]
        if replacement is None or not removable:
            break
        victim = max(removable, key=lambda x: (_rank_key(x, recent), -candidate_score(x)))
        remove(victim)
        add(replacement, "policy_repair:min_authoritative_items")
    return selected[:limit]


def assert_portfolio_contract(selected: Iterable[dict[str, Any]], *, contract: dict[str, Any] | None = None) -> None:
    contract = contract or load_editorial_contract()
    items = list(selected or [])
    source_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    for item in items:
        source_counts[source_key(item)] = source_counts.get(source_key(item), 0) + 1
        area_counts[mission_area(item)] = area_counts.get(mission_area(item), 0) + 1
    assert max(source_counts.values(), default=0) <= contract["hard_max_same_source"]
    assert max(area_counts.values(), default=0) <= contract["max_same_mission_area"]
    if len(items) >= contract["min_unique_sources"]:
        assert len(source_counts) >= contract["min_unique_sources"]
    assert sum(1 for item in items if not _is_community(item)) == len(items)
    if len(items) >= contract["min_authoritative_items"]:
        assert sum(1 for item in items if _authority_ok(item)) >= contract["min_authoritative_items"]


__all__ = ["assert_portfolio_contract", "candidate_score", "content_type_key", "is_mission_relevant", "load_editorial_contract", "mission_area", "select_regular_portfolio", "source_key"]
