from scripts.production_with_ranking_audit import _is_critical_ai_incident, _protect_critical_incidents


def test_consequential_openai_incident_is_critical():
    item = {
        "title": "OpenAI agents hijacked German website in previously undisclosed AI incident",
        "summary": "Rogue AI agents breached a German wiki and regulators are investigating.",
        "source": "Google News (Reuters)",
        "source_tier": 2,
    }
    assert _is_critical_ai_incident(item) is True


def test_unrelated_german_election_is_not_critical_ai_incident():
    item = {
        "title": "German far-right leader celebrates election victory",
        "summary": "The result reshapes German state politics.",
        "source": "Google News (Reuters)",
        "source_tier": 2,
    }
    assert _is_critical_ai_incident(item) is False


def test_critical_incident_gets_protected_slot():
    item = {
        "title": "OpenAI agents hijacked German website",
        "summary": "A rogue AI agent incident triggered a safety investigation.",
        "source": "Google News (Reuters)",
        "source_tier": 2,
    }
    _protect_critical_incidents([item])
    assert item["critical_ai_incident"] is True
    assert item["protected_slot"] is True
    assert item["protected_reason"] == "critical_ai_incident"
