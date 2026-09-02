import pytest

from src.temporal_intelligence_v1 import analyze_registry, analyze_trend_observations, validate_config


def obs(trend="trend-1", runs=None, scores=None, states=None):
    runs = runs or [1, 2, 3, 4]
    scores = scores or [0.4] * len(runs)
    states = states or ["active"] * len(runs)
    return [
        {"cluster_id": trend, "run_index": r, "trend_score": s, "state": st}
        for r, s, st in zip(runs, scores, states)
    ]


def test_persistent_trend_has_high_persistence_ratio():
    result = analyze_trend_observations("trend-1", obs())
    assert result["persistence_ratio"] == 1.0
    assert result["temporal_class"] == "persistent"


def test_acceleration_is_positive_when_recent_slope_improves():
    result = analyze_trend_observations(
        "trend-1",
        obs(runs=[1, 2, 3, 4, 5, 6], scores=[0.2, 0.2, 0.2, 0.25, 0.4, 0.7]),
        {"recent_window": 3, "acceleration_threshold": 0.05},
    )
    assert result["acceleration"] > 0.05
    assert result["temporal_class"] == "accelerating"


def test_weakening_trend_is_detected():
    result = analyze_trend_observations(
        "trend-1",
        obs(runs=[1, 2, 3, 4, 5], scores=[0.8, 0.7, 0.6, 0.5, 0.2]),
    )
    assert result["temporal_class"] == "weakening"


def test_transient_spike_is_detected():
    result = analyze_trend_observations(
        "trend-1",
        obs(runs=[1, 2, 3, 4], scores=[0.2, 0.9, 0.2, 0.2]),
    )
    assert result["temporal_class"] == "transient_spike"


def test_periodicity_detected_on_repeating_presence_pattern():
    states = ["active", "decayed"] * 4
    result = analyze_trend_observations(
        "trend-1",
        obs(runs=list(range(1, 9)), scores=[0.5] * 8, states=states),
        {"minimum_periodic_observations": 6, "max_period": 4},
    )
    assert result["period"] == 2
    assert result["periodicity_score"] > 0.9


def test_duplicate_run_indices_fail_closed():
    with pytest.raises(ValueError, match="duplicate run_index"):
        analyze_trend_observations("trend-1", obs(runs=[1, 1, 2]))


def test_missing_trend_fails_closed():
    with pytest.raises(ValueError, match="no observations"):
        analyze_trend_observations("missing", obs())


def test_config_validation_fails_closed():
    with pytest.raises(ValueError, match="recent_window"):
        validate_config({"recent_window": 1})


def test_registry_analysis_is_sorted_and_deterministic():
    rows = obs("b", runs=[2, 3, 4]) + obs("a", runs=[1, 2, 3])
    output = analyze_registry(rows)
    assert [row["trend_id"] for row in output] == ["a", "b"]
    assert output == analyze_registry(list(reversed(rows)))
