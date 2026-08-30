import pytest

from src.temporal_trend import TrendObservation, TrendState, assess


def test_single_observation_is_emerging():
    result = assess([TrendObservation("2026-08", 0.4, 2, 2)])
    assert result.state == TrendState.EMERGING


def test_growth_with_new_evidence_is_accelerating():
    result = assess([
        TrendObservation("2026-07", 0.40, 2, 2),
        TrendObservation("2026-08", 0.60, 4, 3),
    ])
    assert result.state == TrendState.ACCELERATING
    assert result.acceleration == pytest.approx(0.20)
    assert result.evidence_growth == 2


def test_negative_change_can_be_fading():
    result = assess([
        TrendObservation("2026-07", 0.80, 8, 5),
        TrendObservation("2026-08", 0.60, 8, 5),
    ])
    assert result.state == TrendState.FADING


def test_zero_evidence_is_disconfirmed():
    result = assess([
        TrendObservation("2026-07", 0.10, 1, 1),
        TrendObservation("2026-08", 0.0, 0, 0),
    ])
    assert result.state == TrendState.DISCONFIRMED


def test_periods_must_be_strictly_increasing():
    with pytest.raises(ValueError, match="strictly increasing"):
        assess([
            TrendObservation("2026-08", 0.4, 2, 2),
            TrendObservation("2026-07", 0.5, 3, 2),
        ])


def test_invalid_period_is_rejected():
    with pytest.raises(ValueError, match="YYYY-MM"):
        assess([TrendObservation("August-2026", 0.4, 2, 2)])
