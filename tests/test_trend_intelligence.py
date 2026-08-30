from datetime import date

from src.trend_intelligence import (
    TrendSignal,
    build_clusters,
    cluster_summary,
    lexical_similarity,
    signal_score,
)


def _signal(signal_id: str, title: str, source: str, day: int, domain: str = "ai") -> TrendSignal:
    return TrendSignal(
        signal_id=signal_id,
        title=title,
        summary="agent software engineering future",
        source_id=source,
        source_tier="T1",
        evidence_level="expert_testimony",
        domain=domain,
        observed_on=date(2026, 8, day),
        novelty=0.8,
        strategic_impact=0.9,
        evidence_strength=0.7,
        mission_relevance=0.9,
    )


def test_similarity_is_deterministic():
    left = _signal("a", "agentic software engineering", "s1", 1)
    right = _signal("b", "agentic software development", "s2", 2)
    assert lexical_similarity(left, right) > 0.3
    assert lexical_similarity(left, right) == lexical_similarity(left, right)


def test_same_source_does_not_count_as_independent_evidence():
    signals = [
        _signal("a", "agentic engineering", "same-source", 1),
        _signal("b", "agentic engineering", "same-source", 2),
        _signal("c", "agentic engineering", "other-source", 3),
    ]
    cluster = build_clusters(signals, similarity_threshold=0.3)[0]
    assert cluster.signal_count == 3
    assert cluster.independent_source_count == 2
    assert cluster.state == "emerging"


def test_cross_domain_convergence_is_visible():
    signals = [
        _signal("a", "brain computer interface agent", "s1", 1, "brain_computer_interface"),
        _signal("b", "agentic cognitive systems", "s2", 2, "consciousness_cognition"),
        _signal("c", "AI agents for cognition", "s3", 3, "ai"),
    ]
    cluster = build_clusters(signals, similarity_threshold=0.25)[0]
    summary = cluster_summary(cluster)
    assert len(summary["domains"]) == 3
    assert summary["trend_score"] > 0


def test_signal_score_does_not_use_tier_as_evidence():
    high_tier_weak_evidence = TrendSignal(
        signal_id="a",
        title="frontier claim",
        source_id="trusted",
        source_tier="T1",
        evidence_level="expert_testimony",
        evidence_strength=0.1,
    )
    lower_tier_strong_evidence = TrendSignal(
        signal_id="b",
        title="measured result",
        source_id="research",
        source_tier="T2",
        evidence_level="primary_research",
        evidence_strength=0.9,
    )
    assert signal_score(lower_tier_strong_evidence) > signal_score(high_tier_weak_evidence)
