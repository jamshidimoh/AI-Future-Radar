"""Canonical expert identity/domain signals for the production radar."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PIONEERS_PATH = ROOT / "config" / "pioneers.yaml"
DEEP_SOURCE_PATH = ROOT / "config" / "deep_source_policy.yaml"
REGISTRY_POLICY_PATH = ROOT / "config" / "expert_registry.yaml"

_INTERVIEW_TYPES = {"interview", "podcast", "talk", "lecture", "fireside", "conversation", "discussion", "q&a"}
_TEXT_FIELDS = ("title", "summary", "description", "speaker", "speakers", "watch_person", "leader", "priority_person", "source", "source_name", "source_domain", "content_type", "content_type_detail")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}


def _norm(value: object) -> str:
    text = str(value or "").strip().casefold()
    return text.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").replace("ـ", " ")


def _policy() -> dict[str, Any]:
    return _load_yaml(REGISTRY_POLICY_PATH).get("registry", {})


def _canonical_name(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(_norm(name), name)


def load_expert_registry() -> list[dict[str, Any]]:
    policy = _policy()
    aliases = {_norm(k): str(v).strip() for k, v in (policy.get("duplicate_aliases", {}) or {}).items()}
    raw_people = _load_yaml(PIONEERS_PATH).get("people", []) or []
    registry: dict[str, dict[str, Any]] = {}
    for raw in raw_people:
        if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
            continue
        canonical = _canonical_name(str(raw["name"]).strip(), aliases)
        key = _norm(canonical)
        if key not in registry:
            record = dict(raw)
            record["name"] = canonical
            registry[key] = record
            continue
        current = registry[key]
        if float(raw.get("priority", 0) or 0) > float(current.get("priority", 0) or 0):
            current.update(raw)
        current["name"] = canonical
    return list(registry.values())


def _person_aliases(record: dict[str, Any]) -> tuple[str, ...]:
    name = str(record.get("name") or "").strip()
    if not name:
        return ()
    parts = name.split()
    values = [name]
    if len(parts) >= 2:
        values.append(f"{parts[0]} {parts[-1]}")
    return tuple(dict.fromkeys(_norm(x) for x in values if x))


def _item_text(item: dict[str, Any]) -> str:
    return _norm(" ".join(str(item.get(k) or "")[:4000] for k in _TEXT_FIELDS))


def _explicit_people(item: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for key in ("speaker", "speakers", "watch_person", "leader", "priority_person"):
        raw = str(item.get(key) or "").strip()
        if raw:
            found.update(_norm(x) for x in re.split(r"[,;|/]", raw) if str(x).strip())
    return found


def _matched_people(item: dict[str, Any], registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = _item_text(item)
    explicit = _explicit_people(item)
    title = _norm(item.get("title"))
    interview = str(item.get("content_type") or "").strip().casefold() in _INTERVIEW_TYPES or any(t in title for t in ("interview", "podcast", "conversation", "talk", "مصاحبه", "پادکست", "گفتگو", "گفت‌وگو"))
    matches: list[dict[str, Any]] = []
    for record in registry:
        aliases = _person_aliases(record)
        found = any(alias in explicit for alias in aliases)
        if not found and aliases:
            found = aliases[0] in text
        if not found and interview and len(aliases) > 1:
            found = any(re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", text) for alias in aliases[1:])
        if found:
            matches.append(record)
    return matches


def _record_categories(record: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("category", "categories", "domain", "domains", "specialty", "specialties", "role"):
        value = record.get(key)
        if isinstance(value, list | tuple | set):
            values.extend(str(x) for x in value)
        elif value not in (None, ""):
            values.append(str(value))
    return [_norm(x) for x in values]


def _domain_for(record: dict[str, Any], policy: dict[str, Any]) -> str | None:
    domain_map = policy.get("domain_map", {}) or {}
    for category in _record_categories(record):
        value = domain_map.get(category)
        if value:
            return str(value).strip()
    return None


def _evidence_weight(item: dict[str, Any], deep_policy: dict[str, Any]) -> float:
    weights = deep_policy.get("evidence_weights", {}) or {}
    ctype = str(item.get("content_type") or item.get("content_type_detail") or "").strip().casefold()
    if ctype in weights:
        return float(weights[ctype] or 0)
    source_type = str(item.get("source_type") or "").strip().casefold()
    if source_type in weights:
        return float(weights[source_type] or 0)
    return float(weights.get("reputable_interview", 0.68) or 0.68) if ctype in _INTERVIEW_TYPES else float(weights.get("news_report", 0.45) or 0.45)


def _deep_source_weight(item: dict[str, Any], deep_policy: dict[str, Any]) -> float:
    text = " ".join(_norm(item.get(k)) for k in ("source", "source_name", "source_domain"))
    best = 0.0
    for entry in deep_policy.get("priority_sources", []) or []:
        if not isinstance(entry, dict):
            continue
        name = _norm(entry.get("name"))
        if name and name in text:
            best = max(best, float(entry.get("weight", 0) or 0))
    return best


def expert_features(item: dict[str, Any]) -> dict[str, Any]:
    policy = _policy()
    deep_policy = _load_yaml(DEEP_SOURCE_PATH)
    matches = _matched_people(item, load_expert_registry())
    domains = [x for x in (_domain_for(r, policy) for r in matches) if x]
    explicit_area = _norm(item.get("mission_area") or item.get("category") or "")
    domain_relevant = bool(domains and (not explicit_area or explicit_area in domains or (explicit_area == "mind" and "mind_cognition" in domains) or (explicit_area == "future" and "future_governance" in domains)))
    evidence = _evidence_weight(item, deep_policy)
    source_weight = _deep_source_weight(item, deep_policy)
    priority = max((float(r.get("priority", 0) or 0) for r in matches), default=0.0)
    scientific = max((float(r.get("scientific_authority", 0) or 0) for r in matches), default=0.0)
    future = max((float(r.get("future_vision", 0) or 0) for r in matches), default=0.0)
    impact = max((float(r.get("technology_impact", 0) or 0) for r in matches), default=0.0)
    depth = max(evidence, source_weight)
    deep_context = depth >= 0.68 or str(item.get("content_type") or "").strip().casefold() in _INTERVIEW_TYPES
    expert_score = round(0.45 * priority + 0.20 * scientific * 10 + 0.15 * future * 10 + 0.10 * impact * 10 + 0.10 * depth * 100, 2) if matches else 0.0
    lane_score = max(0.0, min(100.0, expert_score))
    min_lane_score = float((policy.get("scoring", {}) or {}).get("min_lane_score", 70.0) or 70.0)
    expert_deep_lane = bool(matches and domain_relevant and deep_context and lane_score >= min_lane_score)
    max_bonus = float((policy.get("scoring", {}) or {}).get("max_bonus", 8.0) or 8.0)
    bonus = round(min(max_bonus, (lane_score / 100.0) * max_bonus * (1.0 if deep_context else 0.35)), 2) if matches and domain_relevant else 0.0
    return {"people": sorted({str(r["name"]) for r in matches}), "expert_domains": sorted(set(domains)), "expert_priority": priority, "expert_score": lane_score, "deep_source_score": depth, "expert_domain_relevant": domain_relevant, "expert_deep_lane": expert_deep_lane, "expert_bonus": bonus}


def apply_expert_features(item: dict[str, Any]) -> dict[str, Any]:
    features = expert_features(item)
    for key, value in features.items():
        item[key] = value
    if features["expert_bonus"] and not item.get("_expert_signal_applied"):
        try:
            item["signal_score"] = float(item.get("signal_score", 0) or 0) + features["expert_bonus"]
        except (TypeError, ValueError):
            item["signal_score"] = features["expert_bonus"]
        item["_expert_signal_applied"] = True
    return item
