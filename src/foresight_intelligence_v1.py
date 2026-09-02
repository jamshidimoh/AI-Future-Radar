"""Deterministic foresight synthesis from trends, evidence, temporal signals,
and convergence records.

G6 creates auditable drivers, uncertainty, scenarios, and supporting/
contradictory evidence without modifying publication decisions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
DEFAULT_CONFIG: dict[str, Any] = {
    "scenario_count": 3,
    "minimum_evidence": 1,
    "uncertainty_weight": 0.35,
}


def validate_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(dict(config or {}))
    cfg["scenario_count"] = int(cfg["scenario_count"])
    cfg["minimum_evidence"] = int(cfg["minimum_evidence"])
    cfg["uncertainty_weight"] = float(cfg["uncertainty_weight"])
    if cfg["scenario_count"] < 2 or cfg["scenario_count"] > 5:
        raise ValueError("scenario_count must be between 2 and 5")
    if cfg["minimum_evidence"] < 1:
        raise ValueError("minimum_evidence must be >= 1")
    if not 0.0 <= cfg["uncertainty_weight"] <= 1.0:
        raise ValueError("uncertainty_weight must be in [0, 1]")
    return cfg


def _stable_id(prefix: str, payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-g6-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_driver(
    trend: Mapping[str, Any],
    temporal: Mapping[str, Any] | None = None,
    convergence: Sequence[Mapping[str, Any]] | None = None,
    evidence: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    trend_id = str(trend.get("trend_id") or trend.get("cluster_id") or "")
    if not trend_id:
        raise ValueError("trend requires trend_id or cluster_id")
    temporal = temporal or {}
    convergence = list(convergence or [])
    evidence = list(evidence or [])
    related_convergence = [row for row in convergence if trend_id in [str(x) for x in row.get("trend_ids", [])]]
    positive_evidence = [row for row in evidence if str(row.get("relation") or "supports") == "supports"]
    contradictory_evidence = [row for row in evidence if str(row.get("relation") or "" ) == "contradicts"]
    momentum = max(0.0, min(1.0, 0.5 + _float(temporal.get("acceleration")) * 2 + _float(temporal.get("recent_score_slope"))))
    persistence = max(0.0, min(1.0, _float(temporal.get("persistence_ratio"))))
    convergence_strength = max([_float(row.get("convergence_score")) for row in related_convergence] or [0.0])
    support_strength = min(1.0, len(positive_evidence) / max(1, len(evidence))) if evidence else 0.0
    contradiction_ratio = len(contradictory_evidence) / max(1, len(evidence)) if evidence else 0.0
    uncertainty = min(1.0, 0.4 * contradiction_ratio + 0.3 * (1 - persistence) + 0.3 * (1 - support_strength))
    driver_strength = max(0.0, min(1.0, 0.35 * momentum + 0.25 * persistence + 0.25 * convergence_strength + 0.15 * support_strength))
    return {
        "schema_version": SCHEMA_VERSION,
        "driver_id": _stable_id("driver", trend_id),
        "trend_id": trend_id,
        "temporal_class": str(temporal.get("temporal_class") or "unknown"),
        "momentum": round(momentum, 3),
        "persistence": round(persistence, 3),
        "convergence_strength": round(convergence_strength, 3),
        "support_strength": round(support_strength, 3),
        "contradiction_ratio": round(contradiction_ratio, 3),
        "uncertainty": round(uncertainty, 3),
        "driver_strength": round(driver_strength, 3),
        "supporting_evidence_count": len(positive_evidence),
        "contradictory_evidence_count": len(contradictory_evidence),
    }


def synthesize_scenarios(
    drivers: Iterable[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = validate_config(config)
    rows = [dict(driver) for driver in drivers]
    if not rows:
        raise ValueError("at least one driver is required")
    rows.sort(key=lambda row: str(row.get("driver_id") or ""))
    if sum(int(row.get("supporting_evidence_count", 0) or 0) + int(row.get("contradictory_evidence_count", 0) or 0) for row in rows) < cfg["minimum_evidence"]:
        raise ValueError("minimum evidence requirement not met")

    strengths = [max(0.0, min(1.0, _float(row.get("driver_strength")))) for row in rows]
    uncertainties = [max(0.0, min(1.0, _float(row.get("uncertainty")))) for row in rows]
    mean_strength = sum(strengths) / len(strengths)
    mean_uncertainty = sum(uncertainties) / len(uncertainties)
    ordered_ids = [str(row["driver_id"]) for row in rows]

    templates = [
        ("acceleration", 1.0, 0.20, "drivers strengthen and reinforce one another"),
        ("continuity", 0.65, 0.35, "drivers persist but translate into gradual change"),
        ("fragmentation", 0.35, 0.70, "contradictory evidence prevents broad convergence"),
        ("disruption", 1.20, 0.85, "high-strength drivers combine with high uncertainty"),
        ("stall", 0.20, 0.55, "momentum weakens despite surviving signals"),
    ]
    scored = []
    for name, strength_factor, uncertainty_factor, narrative in templates:
        relevance = max(0.0, min(1.0, mean_strength * strength_factor))
        scenario_uncertainty = max(0.0, min(1.0, mean_uncertainty * uncertainty_factor + cfg["uncertainty_weight"] * 0.1))
        probability_proxy = max(0.0, min(1.0, relevance * (1 - 0.35 * scenario_uncertainty)))
        scored.append((probability_proxy, name, scenario_uncertainty, narrative))
    scored.sort(key=lambda item: (-item[0], item[1]))
    scenarios = []
    for probability_proxy, name, scenario_uncertainty, narrative in scored[: cfg["scenario_count"]]:
        scenario_id = _stable_id("scenario", {"drivers": ordered_ids, "name": name})
        scenarios.append({
            "scenario_id": scenario_id,
            "name": name,
            "narrative": narrative,
            "driver_ids": ordered_ids,
            "probability_proxy": round(probability_proxy, 3),
            "uncertainty": round(scenario_uncertainty, 3),
            "evidence_caveat": "probability_proxy is a comparative analytical signal, not a calibrated forecast probability",
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_set_id": _stable_id("scenario-set", {"drivers": ordered_ids, "count": len(scenarios)}),
        "driver_ids": ordered_ids,
        "mean_driver_strength": round(mean_strength, 3),
        "mean_uncertainty": round(mean_uncertainty, 3),
        "scenarios": scenarios,
    }


def validate_foresight(result: Mapping[str, Any]) -> dict[str, Any]:
    if int(result.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported foresight schema_version")
    scenarios = result.get("scenarios")
    drivers = result.get("driver_ids")
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        raise ValueError("foresight requires at least two scenarios")
    if not isinstance(drivers, list) or not drivers:
        raise ValueError("foresight requires driver_ids")
    seen = set()
    for scenario in scenarios:
        sid = str(scenario.get("scenario_id") or "")
        if not sid or sid in seen:
            raise ValueError("invalid scenario identity")
        for key in ("probability_proxy", "uncertainty"):
            value = _float(scenario.get(key), -1)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{key} must be in [0, 1]")
        seen.add(sid)
    return json.loads(json.dumps(result, ensure_ascii=False, sort_keys=True))
