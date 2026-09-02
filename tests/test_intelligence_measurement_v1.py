import pytest

from src.intelligence_measurement_v1 import compare_shadow_windows, measure_intelligence_window, validate_measurement


def test_measurement_marks_window_healthy_and_deterministic():
    record = measure_intelligence_window(
        source_claim_edges=[
            {"source": "s1", "target": "c1", "relation": "supports"},
            {"source": "s2", "target": "c1", "relation": "contradicts"},
        ],
        trends=[{"trend_id": "t1", "domains": ["ai", "robotics"]}],
        temporal=[{"trend_id": "t1", "temporal_class": "accelerating"}],
        convergence=[{"convergence_id": "c1", "convergence_score": 0.8}],
        foresight={"scenarios": [{"scenario_id": "s", "uncertainty": 0.7}, {"scenario_id": "x", "uncertainty": 0.2}]},
    )
    assert record["deterministic"] is True
    assert record["measurement_status"] == "healthy"
    assert record["independent_source_count"] == 2
    assert record["strong_convergence_count"] == 1


def test_shadow_comparison_rejects_excess_contradiction_delta():
    baseline = {"schema_version": 1, "contradiction_rate": 0.1, "deterministic": True}
    candidate = {"schema_version": 1, "contradiction_rate": 0.5, "deterministic": True}
    result = compare_shadow_windows(baseline, candidate)
    assert result["passed"] is False
    assert result["contradiction_rate_delta"] == 0.4


def test_shadow_comparison_requires_determinism():
    baseline = {"schema_version": 1, "contradiction_rate": 0.1, "deterministic": True}
    candidate = {"schema_version": 1, "contradiction_rate": 0.1, "deterministic": False}
    assert compare_shadow_windows(baseline, candidate)["passed"] is False


def test_measurement_counts_domains_and_evidence():
    record = measure_intelligence_window(
        source_claim_edges=[{"source": "s1", "target": "c1", "relation": "supports"}],
        trends=[{"trend_id": "t1", "domains": ["AI", "Quantum"]}, {"trend_id": "t2", "domain": "robotics"}],
    )
    assert record["domain_count"] == 3
    assert record["claim_count"] == 1
    assert record["trend_count"] == 2


def test_invalid_measurement_schema_fails_closed():
    with pytest.raises(ValueError, match="schema_version"):
        validate_measurement({"schema_version": 99})
