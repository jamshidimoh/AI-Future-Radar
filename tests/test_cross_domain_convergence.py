import pytest

from src.cross_domain_convergence import DomainTrend, detect_convergence


def test_two_domains_can_form_meta_trend():
    result = detect_convergence([
        DomainTrend("ai-agents", "ai", 0.9, 5),
        DomainTrend("cognition", "consciousness_cognition", 0.8, 5),
    ])
    assert len(result) == 1
    assert result[0].domains == ("ai", "consciousness_cognition")


def test_weak_evidence_does_not_create_convergence():
    result = detect_convergence([
        DomainTrend("ai-agents", "ai", 0.9, 1),
        DomainTrend("cognition", "consciousness_cognition", 0.9, 1),
    ])
    assert result == []


def test_three_domains_are_supported():
    result = detect_convergence([
        DomainTrend("ai-agents", "ai", 0.9, 5),
        DomainTrend("bci", "brain_computer_interface", 0.9, 5),
        DomainTrend("cognition", "consciousness_cognition", 0.9, 5),
    ], min_domains=3)
    assert len(result) == 1
    assert len(result[0].trend_ids) == 3


def test_invalid_domain_count_is_rejected():
    with pytest.raises(ValueError):
        detect_convergence([], min_domains=1)
