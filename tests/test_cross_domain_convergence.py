import pytest

from src.cross_domain_convergence import DomainTrend, detect_convergence


def test_detects_convergence_across_independent_domains():
    result = detect_convergence([
        DomainTrend("ai-agents", "ai", 0.9, 8),
        DomainTrend("cognition-agents", "consciousness_cognition", 0.8, 6),
    ])
    assert len(result) == 1
    assert result[0].domains == ("ai", "consciousness_cognition")
    assert result[0].trend_ids == ("ai-agents", "cognition-agents")
    assert result[0].convergence_score >= 0.60


def test_weak_trends_do_not_form_meta_trend():
    result = detect_convergence([
        DomainTrend("a", "ai", 0.3, 2),
        DomainTrend("b", "futures_foresight", 0.4, 1),
    ])
    assert result == []


def test_invalid_parameters_fail_closed():
    with pytest.raises(ValueError):
        detect_convergence([], min_domains=1)
    with pytest.raises(ValueError):
        detect_convergence([], min_score=1.1)
