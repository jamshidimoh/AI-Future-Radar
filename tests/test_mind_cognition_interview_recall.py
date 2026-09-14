from src.editorial import filter_ai_relevance


def test_ai_linked_consciousness_is_rescued_into_mind_lane():
    items = [{
        "title": "AI consciousness and the future of mind",
        "summary": "A cognitive science discussion of machine consciousness and artificial intelligence.",
        "category": "mind",
        "content_type": "research",
        "source_tier": 1,
    }]
    result = filter_ai_relevance(items, [])
    assert len(result) == 1
    assert result[0]["mission_area"] == "mind_cognition"
    assert result[0]["topic_family"] == "consciousness_cognition"
    assert result[0]["early_inclusion_reason"] == "mind_cognition_lane"


def test_specialist_ai_interview_is_rescued_even_when_core_topic_taxonomy_is_narrow():
    items = [{
        "title": "Interview: a neuroscientist on consciousness and AI",
        "summary": "Conversation about consciousness, cognition and artificial intelligence.",
        "category": "mind",
        "content_type": "interview",
        "source_tier": 1,
    }]
    result = filter_ai_relevance(items, [])
    assert len(result) == 1
    assert result[0]["early_inclusion_reason"] in {"mind_cognition_lane", "specialist_interview"}
    assert result[0]["_ai_link"] is True


def test_pure_non_ai_philosophy_is_not_rescued():
    items = [{
        "title": "The philosophy of consciousness",
        "summary": "A discussion of consciousness and the philosophy of mind without AI linkage.",
        "category": "mind",
        "content_type": "research",
        "source_tier": 1,
    }]
    result = filter_ai_relevance(items, [])
    assert result == []
