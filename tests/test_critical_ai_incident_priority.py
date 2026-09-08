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


def test_international_law_story_is_not_mistaken_for_ai_incident():
    item = {
        "title": "The Nuremberg trials and capturing Pinochet on international law",
        "summary": "An interview examines international law and accountability.",
        "source": "YouTube - Institute of Art and Ideas",
        "source_tier": 1,
    }
    assert _is_critical_ai_incident(item) is False


def test_gravity_physics_story_is_not_mistaken_for_ai_incident():
    item = {
        "title": "Why gravity is changing our understanding of fundamental physics",
        "summary": "A discussion of gravity and fundamental physics.",
        "source": "YouTube - Institute of Art and Ideas",
        "source_tier": 1,
    }
    assert _is_critical_ai_incident(item) is False


def test_leader_story_is_not_protected_without_independent_technology_relevance():
    item = {
        "title": "Find your purpose after major setbacks: Katie Piper on how to adapt, reinvent and lead",
        "summary": "A leadership and resilience interview from Davos.",
        "source": "World Economic Forum",
        "source_tier": 1,
    }
    _protect_critical_incidents([item])
    assert "critical_ai_incident" not in item
    assert "protected_slot" not in item
    assert "protected_reason" not in item


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
