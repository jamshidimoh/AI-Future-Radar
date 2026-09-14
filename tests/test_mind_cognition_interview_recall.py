from src.editorial import filter_ai_relevance
from src.signal_engine import enrich_with_signal


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
    assert result[0]["protected_mission_lane"] is True


def test_ai_rights_philosophy_is_recalled_even_without_consciousness_keyword():
    items = [{
        "title": "'Sapiens' author says now is the time to resist giving AI rights",
        "summary": "A philosophy and ethics discussion about artificial intelligence, personhood and machine rights.",
        "category": "ai",
        "content_type": "research",
        "source_tier": 2,
    }]
    result = filter_ai_relevance(items, [])
    assert len(result) == 1
    assert result[0]["mission_area"] == "mind_cognition"
    assert result[0]["protected_mission_lane"] is True


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
    assert result[0]["early_inclusion_reason"] == "specialist_interview"
    assert result[0]["_ai_link"] is True
    assert result[0]["protected_mission_lane"] is True


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


def test_protected_mind_lane_gets_deterministic_signal_floor():
    item = {
        "title": "AI philosophy and consciousness",
        "summary": "A study of artificial intelligence, consciousness and philosophy.",
        "mission_area": "mind_cognition",
        "protected_mission_lane": True,
        "source_tier": 1,
        "published": "2026-09-14 10:00",
    }
    result = enrich_with_signal(item)
    assert result["protected_mission_lane"] is True
    assert result["mission_signal_floor_applied"] is True
    assert result["signal_score"] >= 62.0
