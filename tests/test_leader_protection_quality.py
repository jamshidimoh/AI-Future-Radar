from src.story_gate import gate_story_candidates


def test_non_technology_protected_leader_is_dropped():
    result = gate_story_candidates(
        [{
            "title": "Katie Piper on adapting after setbacks",
            "summary": "A leadership and personal resilience discussion.",
            "content_type": "interview",
            "leader": "Katie Piper",
            "is_leader_watch": True,
            "leader_watch_protected": True,
            "protected_content": True,
        }],
        [],
        [],
        [],
    )
    assert result == []


def test_technology_relevant_protected_leader_is_retained():
    result = gate_story_candidates(
        [{
            "title": "Sam Altman discusses the future of AI agents",
            "summary": "An interview about AI agents, model capability and deployment.",
            "content_type": "interview",
            "leader": "Sam Altman",
            "is_leader_watch": True,
            "leader_watch_protected": True,
            "protected_content": True,
            "_ai_link": True,
            "source_tier": 1,
        }],
        [],
        [],
        [],
    )
    assert len(result) == 1
    assert result[0]["protected_content"] is True
