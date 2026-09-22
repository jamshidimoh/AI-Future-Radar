"""Unified, deterministic editorial portfolio selection contract."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.information_gain import (
    editorial_novelty_score,
    information_gain_score,
    max_topic_similarity,
    portfolio_value,
    portfolio_value_with_history,
    topic_fingerprint,
)

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
MISSION_PATH = ROOT / "config" / "mission_policy.yaml"
SELECTION_PATH = ROOT / "config" / "selection_policy.yaml"
_AREA_MAP = {"ai": "ai_core", "ai_core": "ai_core", "quantum": "convergence", "genetics": "convergence", "robotics": "convergence", "humanoid": "convergence", "bio": "convergence", "bci": "convergence", "future": "future_governance", "future_governance": "future_governance", "mind": "mind_cognition", "mind_cognition": "mind_cognition", "convergence": "convergence"}
_RESEARCH_TYPES = {"research", "paper", "study", "preprint"}
_INTERVIEW_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a"}
_COMMUNITY_MARKERS = ("reddit", "community", "aggregator", "techmeme")
_GENERIC_AI_TERMS = {"model", "agent", "reasoning", "ai", "artificial intelligence"}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        logger.error("Editorial contract unavailable at %s: %s", path, exc, exc_info=True)
        return {}


def load_editorial_contract(selection: dict[str, Any] | None = None) -> dict[str, Any]:
    mission_doc = _load_yaml(MISSION_PATH)
    mission = mission_doc.get("mission", {})
    rotation_cfg = mission_doc.get("rotation", {})
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
        "convergence_target": int(mission.get("convergence_target", 0) or 0),
        "mind_cognition_target": int(mission.get("mind_cognition_target", 0) or 0),
        "mind_future_target": int(mission.get("mind_future_target", 0) or 0),
        "research_target": int(mission.get("research_target", 0) or 0),
        "interview_target_max": int(mission.get("interview_target_max", 1) or 0),
        "diversity_quality_floor_ratio": float(selection_cfg.get("diversity_quality_floor_ratio", 0.80) or 0.80),
        "diversity_weight": float(selection_cfg.get("diversity_weight", 8.0) or 8.0),
        "similarity_penalty": float(selection_cfg.get("similarity_penalty", 12.0) or 12.0),
        "entity_repeat_penalty": float(selection_cfg.get("entity_repeat_penalty", 7.0) or 7.0),
        "leader_repeat_penalty": float(selection_cfg.get("leader_repeat_penalty", 10.0) or 10.0),
        "history_topic_penalty": float(selection_cfg.get("history_topic_penalty", 5.0) or 5.0),
        "history_entity_penalty": float(selection_cfg.get("history_entity_penalty", 4.0) or 4.0),
        "freshness_weight": float(selection_cfg.get("freshness_weight", 10.0) or 10.0),
        "freshness_half_life_hours": float(selection_cfg.get("freshness_half_life_hours", 36.0) or 36.0),
        "target_quality_floor_ratio": float(selection_cfg.get("target_quality_floor_ratio", 0.88) or 0.88),
        "required_areas": ("ai_core", "convergence", "mind_cognition", "future_governance"),
        "window_runs": int(rotation_cfg.get("window_runs", 6) or 6),
        "max_same_source_in_window": int(rotation_cfg.get("max_same_source_in_window", 2) or 2),
        "max_same_area_in_window": int(rotation_cfg.get("max_same_area_in_window", 3) or 3),
    }


def source_key(item: dict[str, Any]) -> str:
    return str(item.get("source") or item.get("source_name") or item.get("source_domain") or "unknown").strip().casefold() or "unknown"


def content_type_key(item: dict[str, Any]) -> str:
    return str(item.get("content_type") or "unknown").strip().casefold() or "unknown"


def mission_area(item: dict[str, Any]) -> str:
    explicit = str(item.get("mission_area") or "").strip().casefold()
    if explicit in _AREA_MAP.values() or explicit in {"unclassified", "unknown"}:
        return explicit
    # Specific mission evidence must outrank the legacy broad category label.
    # Otherwise category=ai can incorrectly swallow convergence/mind items.
    matched_area = _keyword_match_area(item)
    if matched_area:
        return matched_area
    category = str(item.get("category") or "").strip().casefold()
    if category in _AREA_MAP:
        return _AREA_MAP[category]
    if item.get("_ai_link") is True or item.get("ai_relevance") is True:
        return "ai_core"
    return "unclassified"

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
    """Apply mission evidence before trusting the legacy category label."""
    explicit = str(item.get("mission_area") or "").strip().casefold()
    if explicit in _AREA_MAP.values():
        if explicit == "ai_core":
            text = _mission_text(item)
            low_signal = _load_yaml(MISSION_PATH).get("low_signal_terms", []) or []
            if any(str(term).strip().casefold() in text for term in low_signal):
                return False
        return True
    matched_area = _keyword_match_area(item)
    if matched_area:
        item["mission_area"] = matched_area
        return True
    category = str(item.get("category") or "").strip().casefold()
    if category in _AREA_MAP:
        item["mission_area"] = _AREA_MAP[category]
        if category == "ai" and strict:
            text = _mission_text(item)
            low_signal = _load_yaml(MISSION_PATH).get("low_signal_terms", []) or []
            if any(str(term).strip().casefold() in text for term in low_signal):
                return False
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
    return any(m in value for m in _COMMUNITY_MARKERS)


def candidate_score(item: dict[str, Any]) -> float:
    for key in ("final_editorial_score", "radar_composite_score", "editorial_score", "mission_score", "signal_score", "score"):
        try:
            value = float(item.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value:
            return value
    return 0.0


def _published_age_hours(item: dict[str, Any]) -> float | None:
    raw = str(item.get("published") or item.get("published_at") or item.get("date") or "").strip()
    if not raw:
        return None
    try:
        value = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0
        # Future-dated fixture/feed timestamps must not receive a freshness bonus.
        if age_hours < -1.0:
            return None
        return max(0.0, age_hours)
    except (TypeError, ValueError):
        return None


def freshness_score(item: dict[str, Any], half_life_hours: float = 36.0) -> float:
    age = _published_age_hours(item)
    if age is None:
        return 0.0
    half_life = max(1.0, float(half_life_hours or 36.0))
    return max(0.0, min(1.0, 2.0 ** (-age / half_life)))


def _safe_float(item: dict[str, Any], key: str) -> float:
    try:
        return float(item.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _rank_key(item: dict[str, Any], recent_source_counts: dict[str, int]) -> tuple:
    source = source_key(item)
    # Uncapped: a source that keeps reappearing keeps accumulating penalty rather
    # than saturating after 3 occurrences. A saturating penalty let a
    # consistently high-scoring source (e.g. one aggregator outscoring everything
    # else) dominate the feed indefinitely, since 3+ repeats always cost the same
    # fixed 6 points regardless of how often it had actually been reused.
    recent_penalty = max(0, int(recent_source_counts.get(source, 0) or 0)) * 2.0
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


def _annotate_information_gain(item: dict[str, Any], selected: list[dict[str, Any]], contract: dict[str, Any], history_signatures: Iterable[dict[str, Any] | str] = ()) -> dict[str, Any]:
    item["topic_fingerprint"] = topic_fingerprint(item)
    item["information_gain_score"] = information_gain_score(item, selected)
    item["topic_similarity_to_selected"] = round(max_topic_similarity(item, selected), 3)
    novelty = editorial_novelty_score(item, selected, history_signatures)
    item["current_entity_overlap"] = novelty["current_entity_overlap"]
    item["history_topic_similarity"] = novelty["history_topic_similarity"]
    item["history_entity_overlap"] = novelty["history_entity_overlap"]
    freshness_half_life = float(contract.get("freshness_half_life_hours", 24.0) or 24.0)
    freshness_weight = float(contract.get("freshness_weight", 10.0) or 10.0)
    item["freshness_score"] = round(freshness_score(item, freshness_half_life), 4)
    item["freshness_weighted_score"] = round(item["freshness_score"] * freshness_weight, 3)
    item["portfolio_value_score"] = round(
        portfolio_value_with_history(
            item, selected, history_signatures,
            diversity_weight=contract["diversity_weight"],
            similarity_penalty=contract["similarity_penalty"],
            entity_repeat_penalty=contract["entity_repeat_penalty"],
            leader_repeat_penalty=contract["leader_repeat_penalty"],
            history_topic_penalty=contract["history_topic_penalty"],
            history_entity_penalty=contract["history_entity_penalty"],
        ),
        3,
    )
    return item


class _Portfolio:
    def __init__(self, *, contract: dict[str, Any], limit: int, source_cap: int, type_cap: int, recent: dict[str, int], mission_aware: bool, window_source_counts: dict[str, int] | None = None, window_area_counts: dict[str, int] | None = None, history_signatures: Iterable[dict[str, Any] | str] = ()):
        self.history_signatures = list(history_signatures or ())
        self.selected: list[dict[str, Any]] = []
        self.selected_ids: set[int] = set()
        self.source_counts: dict[str, int] = {}
        self.type_counts: dict[str, int] = {}
        self.area_counts: dict[str, int] = {}
        self.interview_count = 0
        self.contract = contract
        self.recent = recent
        self.limit = limit
        self.source_cap = source_cap
        self.type_cap = type_cap
        self.mission_aware = mission_aware
        self.window_source_counts = window_source_counts or {}
        self.window_area_counts = window_area_counts or {}

    def admissible(self, item: dict[str, Any], *, repeat_source: bool, ignore_type_cap: bool = False, ignore_window_cap: bool = False) -> bool:
        source, ctype, area = source_key(item), content_type_key(item), mission_area(item)
        if not ignore_type_cap and self.type_counts.get(ctype, 0) >= self.type_cap:
            return False
        if self.mission_aware and _is_interview(item) and self.interview_count >= self.contract["interview_target_max"] > 0:
            return False
        if self.mission_aware and self.area_counts.get(area, 0) >= self.contract["max_same_mission_area"]:
            return False
        if not ignore_window_cap:
            # Cross-run rotation cap: a single source/area must not keep dominating
            # the feed across the last `window_runs` runs, independent of how well
            # it scores within a single run. This is a hard cap with a bypass
            # fallback (see _fill_by_portfolio_value / _backfill_repeat_sources)
            # so a starved candidate pool never blocks publication entirely.
            if self.window_source_counts.get(source, 0) >= int(self.contract.get("max_same_source_in_window", 2) or 2):
                return False
            if self.mission_aware and self.window_area_counts.get(area, 0) >= int(self.contract.get("max_same_area_in_window", 3) or 3):
                return False
        current_source = self.source_counts.get(source, 0)
        return current_source < self.source_cap if repeat_source else current_source == 0

    def add(self, item: dict[str, Any], reason: str) -> None:
        _annotate_information_gain(item, self.selected, self.contract, self.history_signatures)
        source, ctype, area = source_key(item), content_type_key(item), mission_area(item)
        self.selected.append(item)
        self.selected_ids.add(id(item))
        self.source_counts[source] = self.source_counts.get(source, 0) + 1
        self.type_counts[ctype] = self.type_counts.get(ctype, 0) + 1
        if self.mission_aware:
            self.area_counts[area] = self.area_counts.get(area, 0) + 1
        if _is_interview(item):
            self.interview_count += 1
        item["mission_selection_reason"] = reason

    def remove(self, item: dict[str, Any]) -> None:
        self.selected.remove(item)
        self.selected_ids.remove(id(item))
        self.source_counts[source_key(item)] -= 1
        self.type_counts[content_type_key(item)] -= 1
        if self.mission_aware:
            self.area_counts[mission_area(item)] -= 1
        if _is_interview(item):
            self.interview_count -= 1

    def best(self, pool: list[dict[str, Any]], *, prefer_research: bool = False) -> dict[str, Any] | None:
        candidates = [x for x in pool if self.admissible(x, repeat_source=False)]
        if not candidates:
            return None
        if prefer_research:
            research_first = [x for x in candidates if _is_research(x)]
            if research_first:
                candidates = research_first
        return max(candidates, key=self.value_key)

    def value_key(self, item: dict[str, Any]) -> tuple:
        return (
            portfolio_value_with_history(
                item,
                self.selected,
                self.history_signatures,
                diversity_weight=self.contract["diversity_weight"],
                similarity_penalty=self.contract["similarity_penalty"],
                entity_repeat_penalty=self.contract["entity_repeat_penalty"],
                leader_repeat_penalty=self.contract["leader_repeat_penalty"],
                history_topic_penalty=self.contract["history_topic_penalty"],
                history_entity_penalty=self.contract["history_entity_penalty"],
            ),
            -_rank_key(item, self.recent)[0],
            candidate_score(item),
            freshness_score(item, float(self.contract.get("freshness_half_life_hours", 24.0) or 24.0)) * float(self.contract.get("freshness_weight", 10.0) or 10.0),
            str(item.get("published") or item.get("published_at") or ""),
        )


def _eligible_candidates(candidates: Iterable[dict[str, Any]], contract: dict[str, Any], strict_relevance: bool) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for raw in list(candidates or []):
        item = dict(raw)
        if _is_community(item) and contract["community_max"] <= 0:
            continue
        if not is_mission_relevant(item, strict=strict_relevance):
            continue
        item["mission_area"] = mission_area(item)
        eligible.append(item)
    return eligible


def _quality_floor_candidate(p: _Portfolio, pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [x for x in pool if id(x) not in p.selected_ids and p.admissible(x, repeat_source=False)]
    if not candidates:
        return None
    top_score = max((candidate_score(x) for x in candidates), default=0.0)
    if top_score <= 0.0:
        return None
    floor = max(0.0, min(1.0, float(p.contract.get("diversity_quality_floor_ratio", 0.80))))
    viable = [x for x in candidates if candidate_score(x) >= top_score * floor]
    if not viable:
        viable = [max(candidates, key=lambda x: candidate_score(x))]
    unseen_area = [x for x in viable if mission_area(x) not in p.area_counts]
    if unseen_area:
        viable = unseen_area
    freshness_weight = float(p.contract.get("freshness_weight", 10.0) or 10.0)
    freshness_half_life = float(p.contract.get("freshness_half_life_hours", 24.0) or 24.0)
    return max(
        viable,
        key=lambda x: (
            portfolio_value(
                x,
                p.selected,
                diversity_weight=p.contract["diversity_weight"],
                similarity_penalty=p.contract["similarity_penalty"],
            )
            + freshness_score(x, freshness_half_life) * freshness_weight,
            candidate_score(x),
            _safe_float(x, "evidence_strength"),
            str(x.get("published", "")),
        ),
    )


def _fill_mission_targets(p: _Portfolio, ordered: list[dict[str, Any]]) -> None:
    if not p.mission_aware or p.limit <= 0:
        return
    for _ in range(min(p.contract["ai_core_target_min"], p.limit)):
        candidates = [x for x in ordered if mission_area(x) == "ai_core" and id(x) not in p.selected_ids and p.admissible(x, repeat_source=False)]
        if not candidates:
            candidates = [x for x in ordered if mission_area(x) == "ai_core" and id(x) not in p.selected_ids and p.admissible(x, repeat_source=False, ignore_type_cap=True)]
        if not candidates:
            # ai_core is normally the deepest candidate pool; only reach past the
            # rotation window cap here if nothing else qualifies at all.
            candidates = [x for x in ordered if mission_area(x) == "ai_core" and id(x) not in p.selected_ids and p.admissible(x, repeat_source=False, ignore_type_cap=True, ignore_window_cap=True)]
        candidate = max(candidates, key=lambda x: (candidate_score(x), _safe_float(x, "evidence_strength")), default=None)
        if candidate is None:
            break
        p.add(candidate, "mission_target:ai_core")

    if p.contract.get("mind_cognition_target", 0) > 0:
        targets = (
            ("convergence_target", lambda x: mission_area(x) == "convergence"),
            ("mind_cognition_target", lambda x: mission_area(x) == "mind_cognition"),
            ("research_target", _is_research),
        )
    else:
        targets = (
            ("convergence_target", lambda x: mission_area(x) == "convergence"),
            ("mind_future_target", lambda x: mission_area(x) in {"mind_cognition", "future_governance"}),
            ("research_target", _is_research),
        )

    for target_key, area_predicate in targets:
        for _ in range(min(p.contract.get(target_key, 0), max(0, p.limit - len(p.selected)))):
            pool = [x for x in ordered if area_predicate(x) and id(x) not in p.selected_ids and p.admissible(x, repeat_source=False)]
            if not pool:
                pool = [x for x in ordered if area_predicate(x) and id(x) not in p.selected_ids and p.admissible(x, repeat_source=False, ignore_type_cap=True)]
            if not pool:
                # These lanes (convergence / mind_cognition / future_governance / research)
                # are already the scarcest candidate pools. The rotation window cap exists
                # to stop a dominant source from crowding out other sources, not to make an
                # already-rare lane even harder to fill — so it is relaxed here as a last resort.
                pool = [x for x in ordered if area_predicate(x) and id(x) not in p.selected_ids and p.admissible(x, repeat_source=False, ignore_type_cap=True, ignore_window_cap=True)]
            if not pool:
                break
            # Explicit mission targets are coverage controls, not opportunistic
            # diversity suggestions. Once a candidate passes the normal eligibility
            # gates above (mission relevance, community policy, source/type caps,
            # interview cap, and rotation-window constraints), fill the requested
            # target even when a stronger non-target candidate exists. The previous
            # implementation compared the target against the global highest score,
            # including candidates that were not admissible under the current source
            # or content-type constraints, so a valid convergence/mind/future target
            # could be dropped systematically.
            candidate = max(pool, key=lambda x: (candidate_score(x), _safe_float(x, "evidence_strength")), default=None)
            if candidate is None:
                break

            # Mission targets are coverage opportunities, not unconditional slots.
            # Keep them only when they remain competitive with the strongest
            # currently admissible alternative under the diversity quality floor.
            # This prevents weak Mind/Future/Convergence stories from displacing
            # materially stronger mainstream candidates while preserving genuine
            # cross-domain coverage when a solid candidate exists.
            top_global = max(
                (
                    candidate_score(x)
                    for x in ordered
                    if id(x) not in p.selected_ids
                    and p.admissible(x, repeat_source=False)
                ),
                default=0.0,
            )
            floor = max(
                0.0,
                min(
                    1.0,
                    float(p.contract.get("diversity_quality_floor_ratio", 0.80) or 0.80),
                ),
            )
            if top_global > 0.0 and candidate_score(candidate) < top_global * floor:
                break

            candidate_area = mission_area(candidate)
            if candidate_area == "mind_cognition":
                reason = "mission_target:mind_cognition"
            elif candidate_area == "future_governance":
                reason = "mission_target:future_governance"
            else:
                reason = f"mission_target:{target_key.removesuffix('_target')}"
            p.add(candidate, reason)


def _fill_by_portfolio_value(p: _Portfolio, eligible: list[dict[str, Any]]) -> None:
    while len(p.selected) < p.limit:
        unique_pool = [x for x in eligible if id(x) not in p.selected_ids and p.admissible(x, repeat_source=False)]
        if not unique_pool:
            # The rotation window cap (see admissible()) is a hard cap by design,
            # but it must never be the sole reason a run publishes nothing. If
            # relaxing only the window cap recovers candidates, use it as a
            # last-resort bypass before giving up on this slot.
            unique_pool = [x for x in eligible if id(x) not in p.selected_ids and p.admissible(x, repeat_source=False, ignore_window_cap=True)]
            if not unique_pool:
                break
        best_item = _quality_floor_candidate(p, unique_pool)
        if best_item is None:
            break
        if p.mission_aware and mission_area(best_item) == "ai_core" and p.area_counts.get("ai_core", 0) >= p.contract["ai_core_target_max"]:
            alternative = [x for x in unique_pool if mission_area(x) != "ai_core"]
            if alternative:
                alt = _quality_floor_candidate(p, alternative)
                if alt is not None:
                    best_item = alt
                else:
                    break
            else:
                break
        p.add(best_item, "portfolio_value")


def _backfill_repeat_sources(p: _Portfolio, eligible: list[dict[str, Any]]) -> None:
    if p.source_cap <= 1:
        return
    while len(p.selected) < p.limit:
        pool = [x for x in eligible if id(x) not in p.selected_ids and p.admissible(x, repeat_source=True)]
        if not pool:
            pool = [x for x in eligible if id(x) not in p.selected_ids and p.admissible(x, repeat_source=True, ignore_window_cap=True)]
            if not pool:
                break
        top_score = max((candidate_score(x) for x in pool), default=0.0)
        floor = max(0.0, min(1.0, float(p.contract.get("diversity_quality_floor_ratio", 0.80))))
        viable = [x for x in pool if top_score <= 0 or candidate_score(x) >= top_score * floor]
        if not viable:
            viable = [max(pool, key=candidate_score)]
        for item in viable:
            _annotate_information_gain(item, p.selected, p.contract)
        best_item = max(viable, key=lambda x: (portfolio_value(x, p.selected, diversity_weight=p.contract["diversity_weight"], similarity_penalty=p.contract["similarity_penalty"]), candidate_score(x)))
        p.add(best_item, "adaptive_source_backfill")


def _repair_min_authoritative(p: _Portfolio, eligible: list[dict[str, Any]]) -> None:
    auth_required = min(p.contract["min_authoritative_items"], len(p.selected))
    while p.mission_aware and sum(_authority_ok(x) for x in p.selected) < auth_required:
        removable = [x for x in p.selected if not _authority_ok(x)]
        if not removable:
            break

        def _is_mission_target(x: dict[str, Any]) -> bool:
            return str(x.get("mission_selection_reason") or "").startswith("mission_target:")

        authoritative = [
            x for x in eligible
            if id(x) not in p.selected_ids
            and _authority_ok(x)
            and p.admissible(x, repeat_source=False)
        ]
        if not authoritative:
            break

        def _replacement_for(victim: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
            same_area = [
                x for x in authoritative
                if mission_area(x) == mission_area(victim)
            ]
            replacement_pool = same_area or authoritative
            if not replacement_pool:
                return None, False
            replacement = max(
                replacement_pool,
                key=lambda x: (
                    candidate_score(x),
                    _safe_float(x, "evidence_strength"),
                    freshness_score(
                        x,
                        float(p.contract.get("freshness_half_life_hours", 24.0) or 24.0),
                    ),
                    _rank_key(x, p.recent),
                ),
            )
            return replacement, bool(same_area)

        # Choose the repair pair that preserves mission area first and minimizes
        # quality loss. This is important when several non-authoritative mission
        # targets were deliberately selected: do not replace a stronger target
        # with a much weaker authoritative item when another lane can be repaired
        # with less information loss.
        repair_options: list[tuple[tuple[Any, ...], dict[str, Any], dict[str, Any]]] = []
        for victim in removable:
            replacement, same_area = _replacement_for(victim)
            if replacement is None:
                continue
            quality_delta = candidate_score(replacement) - candidate_score(victim)
            option_key = (
                1 if same_area else 0,
                quality_delta,
                -candidate_score(victim),
                _safe_float(replacement, "evidence_strength"),
                str(replacement.get("published") or ""),
            )
            repair_options.append((option_key, victim, replacement))

        if not repair_options:
            break

        _, victim, replacement = max(repair_options, key=lambda row: row[0])
        # Recompute the authoritative candidate pool after removing the victim so
        # a replacement from the victim's former source can become admissible.
        p.remove(victim)
        authoritative_after = [
            x for x in eligible
            if id(x) not in p.selected_ids
            and _authority_ok(x)
            and p.admissible(x, repeat_source=False)
        ]
        same_area_after = [
            x for x in authoritative_after
            if mission_area(x) == mission_area(victim)
        ]
        replacement_pool = same_area_after or authoritative_after
        if not replacement_pool:
            p.add(victim, str(victim.get("mission_selection_reason") or ""))
            break
        replacement = max(
            replacement_pool,
            key=lambda x: (
                candidate_score(x),
                _safe_float(x, "evidence_strength"),
                freshness_score(
                    x,
                    float(p.contract.get("freshness_half_life_hours", 24.0) or 24.0),
                ),
                _rank_key(x, p.recent),
            ),
        )
        p.add(replacement, "policy_repair:min_authoritative_items")


def _annotate_final_information_gain(selected: list[dict[str, Any]]) -> None:
    for item in selected:
        item["portfolio_information_gain"] = information_gain_score(item, [x for x in selected if x is not item])


def select_regular_portfolio(candidates: Iterable[dict[str, Any]], *, max_posts: int, max_per_source: int, max_per_type: int, recent_source_counts: dict[str, int] | None = None, contract: dict[str, Any] | None = None, mission_aware: bool = True, strict_relevance: bool = False, window_source_counts: dict[str, int] | None = None, window_area_counts: dict[str, int] | None = None, history_signatures: Iterable[dict[str, Any] | str] = ()) -> list[dict[str, Any]]:
    contract = contract or load_editorial_contract()
    limit = max(0, int(max_posts or 0))
    source_cap = max(1, int(max_per_source or contract["hard_max_same_source"]))
    type_cap = max(1, int(max_per_type or 1))
    recent = recent_source_counts or {}
    history = list(history_signatures or ())
    eligible = _eligible_candidates(candidates, contract, strict_relevance)
    ordered = sorted(eligible, key=lambda x: _rank_key(x, recent))
    portfolio = _Portfolio(contract=contract, limit=limit, source_cap=source_cap, type_cap=type_cap, recent=recent, mission_aware=mission_aware, window_source_counts=window_source_counts, window_area_counts=window_area_counts, history_signatures=history)
    _fill_mission_targets(portfolio, ordered)
    _fill_by_portfolio_value(portfolio, eligible)
    _backfill_repeat_sources(portfolio, eligible)
    _repair_min_authoritative(portfolio, eligible)
    _annotate_final_information_gain(portfolio.selected)
    return portfolio.selected[:limit]


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
    assert sum(_authority_ok(x) for x in items) >= min(contract["min_authoritative_items"], len(items))
    assert sum(_is_community(x) for x in items) <= contract["community_max"]
