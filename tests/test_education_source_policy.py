from education_source_policy import assess_source, validate_current_sources


def _src(url, status="dated_current", score=90, org=None):
    return {
        "url": url,
        "current_verified": True,
        "current_status": status,
        "authority_score": score,
        "organization": org,
    }


def test_two_independent_current_sources_are_required():
    ok, _, reason = validate_current_sources([
        _src("https://developers.google.com/a", org="google"),
        _src("https://ai.google.dev/b", org="google"),
    ])
    assert not ok
    assert "independent" in reason


def test_two_independent_current_sources_pass():
    ok, verified, reason = validate_current_sources([
        _src("https://nist.gov/a", org="nist", score=95),
        _src("https://developers.google.com/b", org="google", score=90),
    ])
    assert ok
    assert reason == "ok"
    assert len(verified) == 2


def test_maintained_official_documentation_can_be_current_without_embedded_year():
    result = assess_source(
        url="https://developers.google.com/machine-learning/glossary",
        reachable=True,
        detected_year=None,
        declared_year=None,
    )
    assert result["current"] is True
    assert result["status"] == "maintained_current"


def test_old_detected_date_overrides_newer_declared_year():
    result = assess_source(
        url="https://example.edu/old-paper",
        reachable=True,
        detected_year=2024,
        declared_year=2026,
    )
    assert result["current"] is False
    assert result["status"] == "outdated"


def test_anthropic_agent_evals_is_current_despite_historical_page_date_noise():
    result = assess_source(
        url="https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents",
        reachable=True,
        detected_year=2025,
        declared_year=2026,
    )
    assert result["current"] is True
    assert result["status"] == "dated_current"
    assert result["year"] == 2026


def test_unrelated_outdated_source_remains_rejected():
    result = assess_source(
        url="https://example.com/old-education-source",
        reachable=True,
        detected_year=2024,
        declared_year=2024,
    )
    assert result["current"] is False
    assert result["status"] == "outdated"
