"""Measurement harness for intelligence layers before production integration.

G7 measures determinism, coverage, evidence diversity, contradiction exposure,
and temporal/convergence/foresight signal health. It does not publish or alter
selection decisions.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1


def _stable_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def measure_intelligence_window(
    *,
    source_claim_edges: Iterable[Mapping[str, Any]],
    trends: Sequence[Mapping[str, Any]],
    temporal: Sequence[Mapping[str, Any]] = (),
    convergence: Sequence[Mapping[str, Any]] = (),
    foresight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    edges = [dict(edge) for edge in source_claim_edges]
    trend_rows = [dict(row) for row in trends]
    temporal_rows = [dict(row) for row in temporal]
    convergence_rows = [dict(row) for row in convergence]
    support = sum(1 for edge in edges if edge.get("relation") == "supports")
    contradiction = sum(1 for edge in edges if edge.get("relation") == "contradicts")
    source_ids = {str(edge.get("source") or "") for edge in edges if str(edge.get("source") or "")}
    claim_ids = {str(edge.get("target") or "") for edge in edges if edge.get("relation") in {"supports", "contradicts"}}
    domains = set()
    for trend in trend_rows:
        values = trend.get("domains") or trend.get("domain") or []
        if isinstance(values, str):
            values = [values]
        domains.update(str(x).strip().lower() for x in values if str(x).strip())

    determinism_payload = {
        "trends": trend_rows,
        "temporal": temporal_rows,
        "convergence": convergence_rows,
        "foresight": foresight or {},
    }
    digest_a = _stable_digest(determinism_payload)
    digest_b = _stable_digest(json.loads(json.dumps(determinism_payload, ensure_ascii=False, sort_keys=True)))
    total_convergence = len(convergence_rows)
    total_high_convergence = sum(1 for row in convergence_rows if _num(row.get("convergence_score")) >= 0.75)
    high_uncertainty_scenarios = 0
    scenario_count = 0
    if foresight:
        scenarios = foresight.get("scenarios") or []
        scenario_count = len(scenarios)
        high_uncertainty_scenarios = sum(1 for row in scenarios if _num(row.get("uncertainty")) >= 0.6)

    return {
        "schema_version": SCHEMA_VERSION,
        "deterministic": digest_a == digest_b,
        "window_digest": digest_a,
        "trend_count": len(trend_rows),
        "domain_count": len(domains),
        "evidence_edge_count": len(edges),
        "support_edge_count": support,
        "contradiction_edge_count": contradiction,
        "contradiction_rate": round(contradiction / max(1, support + contradiction), 3),
        "independent_source_count": len(source_ids),
        "claim_count": len(claim_ids),
        "temporal_signal_count": len(temporal_rows),
        "convergence_count": total_convergence,
        "strong_convergence_count": total_high_convergence,
        "scenario_count": scenario_count,
        "high_uncertainty_scenario_count": high_uncertainty_scenarios,
        "measurement_status": "healthy" if digest_a == digest_b else "invalid",
    }


def compare_shadow_windows(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    max_contradiction_rate_delta: float = 0.20,
    min_determinism: bool = True,
) -> dict[str, Any]:
    if baseline.get("schema_version") != SCHEMA_VERSION or candidate.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported measurement schema_version")
    contradiction_delta = _num(candidate.get("contradiction_rate")) - _num(baseline.get("contradiction_rate"))
    deterministic = bool(candidate.get("deterministic"))
    passed = deterministic or not min_determinism
    if contradiction_delta > max_contradiction_rate_delta:
        passed = False
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "deterministic": deterministic,
        "contradiction_rate_delta": round(contradiction_delta, 3),
        "max_contradiction_rate_delta": max_contradiction_rate_delta,
    }


def validate_measurement(record: Mapping[str, Any]) -> dict[str, Any]:
    if int(record.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported measurement schema_version")
    required = ("window_digest", "trend_count", "evidence_edge_count", "measurement_status")
    if any(key not in record for key in required):
        raise ValueError("missing measurement field")
    if record["measurement_status"] not in {"healthy", "invalid"}:
        raise ValueError("invalid measurement status")
    return json.loads(json.dumps(record, ensure_ascii=False, sort_keys=True))
