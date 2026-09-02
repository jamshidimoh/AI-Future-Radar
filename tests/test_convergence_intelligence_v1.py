import pytest

from src.convergence_intelligence_v1 import (
    analyze_convergence,
    analyze_convergence_pair,
    validate_config,
    validate_convergence,
)


def trend(trend_id, domains, claims, sources, title="AI and biology convergence"):
    return {
        "trend_id": trend_id,
        "domains": domains,
        "claim_ids": claims,
        "source_ids": sources,
        "title": title,
        "summary": title,
    }


def test_cross_domain_pair_requires_independent_evidence_and_scores():
    left = trend("t1", ["ai"], ["c1", "c2"], ["s1", "s2"])
    right = trend("t2", ["bio"], ["c2", "c3"], ["s3"])
    result = analyze_convergence_pair(left, right)
    assert result is not None
    assert result["domains"] == ["ai", "bio"]
    assert result["shared_claim_ids"] == ["c2"]
    assert result["independent_source_count"] == 3
    assert result["convergence_score"] >= 0.5


def test_same_domain_is_not_convergence():
    a = trend("a", ["ai"], ["c1"], ["s1"])
    b = trend("b", ["ai"], ["c1"], ["s2"])
    assert analyze_convergence_pair(a, b) is None


def test_missing_independent_sources_fail_closed():
    a = trend("a", ["ai"], ["c1"], ["s1"])
    b = trend("b", ["bio"], ["c1"], ["s1"])
    assert analyze_convergence_pair(a, b) is None


def test_textual_anchor_can_support_convergence_without_shared_claim_id():
    a = trend("a", ["quantum"], [], ["s1"], title="Quantum sensing for brain imaging")
    b = trend("b", ["bci"], [], ["s2"], title="Brain imaging using quantum sensing")
    result = analyze_convergence_pair(a, b, {"minimum_shared_claims": 1, "convergence_threshold": 0.25})
    assert result is not None
    assert "brain" in result["shared_anchor_tokens"]


def test_weak_pair_is_rejected_by_threshold():
    a = trend("a", ["ai"], ["c1"], ["s1"], title="AI")
    b = trend("b", ["robotics"], ["c2"], ["s2"], title="Robotics")
    assert analyze_convergence_pair(a, b) is None


def test_convergence_output_is_deterministic_and_sorted():
    rows = [
        trend("b", ["robotics"], ["c1"], ["s2"], title="AI robotics autonomy"),
        trend("a", ["ai"], ["c1"], ["s1"], title="AI robotics autonomy"),
        trend("c", ["bio"], ["c1"], ["s3"], title="AI robotics autonomy"),
    ]
    first = analyze_convergence(rows, {"convergence_threshold": 0.45})
    second = analyze_convergence(list(reversed(rows)), {"convergence_threshold": 0.45})
    assert first == second
    assert first
    assert all(record["domains"] and len(record["domains"]) >= 2 for record in first)


def test_validate_convergence_rejects_invalid_record():
    with pytest.raises(ValueError, match="at least two domains"):
        validate_convergence(
            [{"schema_version": 1, "convergence_id": "x", "trend_ids": ["a", "b"], "domains": ["ai"], "convergence_score": 0.7}]
        )


def test_validate_convergence_rejects_duplicate_ids():
    record = {"schema_version": 1, "convergence_id": "x", "trend_ids": ["a", "b"], "domains": ["ai", "bio"], "convergence_score": 0.7}
    with pytest.raises(ValueError, match="invalid convergence identity"):
        validate_convergence([record, dict(record)])


def test_config_fails_closed():
    with pytest.raises(ValueError, match="minimum_domains"):
        validate_config({"minimum_domains": 1})
