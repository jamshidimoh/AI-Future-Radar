import pytest

from src.foresight_intelligence_v1 import build_driver, synthesize_scenarios, validate_config, validate_foresight


def temporal(persistence=1.0, acceleration=0.1, recent_slope=0.05, cls="accelerating"):
    return {
        "persistence_ratio": persistence,
        "acceleration": acceleration,
        "recent_score_slope": recent_slope,
        "temporal_class": cls,
    }


def test_driver_combines_temporal_convergence_and_evidence():
    result = build_driver(
        {"trend_id": "t1"},
        temporal(),
        [{"trend_ids": ["t1", "t2"], "convergence_score": 0.8}],
        [{"relation": "supports"}, {"relation": "contradicts"}],
    )
    assert result["driver_id"]
    assert result["driver_strength"] > 0
    assert result["uncertainty"] > 0


def test_driver_requires_trend_identity():
    with pytest.raises(ValueError, match="trend requires"):
        build_driver({})


def test_scenario_set_contains_multiple_auditable_scenarios():
    drivers = [
        {"driver_id": "d1", "driver_strength": 0.8, "uncertainty": 0.2, "supporting_evidence_count": 3, "contradictory_evidence_count": 1},
        {"driver_id": "d2", "driver_strength": 0.6, "uncertainty": 0.4, "supporting_evidence_count": 2, "contradictory_evidence_count": 0},
    ]
    result = synthesize_scenarios(drivers)
    assert len(result["scenarios"]) == 3
    assert len({s["scenario_id"] for s in result["scenarios"]}) == 3
    assert all("evidence_caveat" in s for s in result["scenarios"])


def test_scenario_synthesis_is_deterministic_under_input_order():
    drivers = [
        {"driver_id": "d2", "driver_strength": 0.6, "uncertainty": 0.4, "supporting_evidence_count": 2, "contradictory_evidence_count": 0},
        {"driver_id": "d1", "driver_strength": 0.8, "uncertainty": 0.2, "supporting_evidence_count": 3, "contradictory_evidence_count": 1},
    ]
    assert synthesize_scenarios(drivers) == synthesize_scenarios(list(reversed(drivers)))


def test_foresight_fails_without_evidence():
    with pytest.raises(ValueError, match="minimum evidence"):
        synthesize_scenarios([{"driver_id": "d1", "driver_strength": 0.5, "uncertainty": 0.5, "supporting_evidence_count": 0, "contradictory_evidence_count": 0}])


def test_invalid_config_fails_closed():
    with pytest.raises(ValueError, match="scenario_count"):
        validate_config({"scenario_count": 1})


def test_validation_rejects_malformed_scenario():
    with pytest.raises(ValueError, match="invalid scenario identity"):
        validate_foresight({"schema_version": 1, "driver_ids": ["d1"], "scenarios": [{"scenario_id": ""}, {"scenario_id": "x"}]})


def test_validation_accepts_valid_result():
    result = synthesize_scenarios([
        {"driver_id": "d1", "driver_strength": 0.7, "uncertainty": 0.3, "supporting_evidence_count": 1, "contradictory_evidence_count": 0},
    ])
    assert validate_foresight(result) == result
