from src.signal_engine import calculate_signal_score, classify_signal, enrich_with_signal


def test_signal_vector_has_expected_dimensions():
    item = {
        "title": "New reasoning model benchmark shows major improvement",
        "summary": "Researchers report new results and experiments.",
        "content_type": "research",
        "source_tier": 1,
        "official": True,
    }
    result = enrich_with_signal(item)
    assert set(result["signal_vector"]) == {
        "freshness", "novelty", "future_impact", "technical_significance",
        "strategic_relevance", "expert_influence", "evidence_strength",
        "trend_alignment", "source_quality",
    }
    assert 0 <= result["signal_score"] <= 100


def test_expert_influence_does_not_dominate_weak_content():
    weak = {
        "title": "Interview with major AI leader",
        "summary": "A casual discussion with no new claims.",
        "content_type": "interview",
        "expert_influence": 10,
        "source_tier": 1,
    }
    strong = {
        "title": "New architecture benchmark and experimental results",
        "summary": "Researchers report a novel method with measured findings and benchmark improvements.",
        "content_type": "research",
        "source_tier": 1,
        "official": True,
    }
    weak_score = enrich_with_signal(weak)["signal_score"]
    strong_score = enrich_with_signal(strong)["signal_score"]
    assert strong_score > weak_score


def test_leader_interview_is_recognized_as_interview_signal():
    item = {
        "title": "Conversation with Demis Hassabis on the future of AI",
        "summary": "Discussion about AGI, research trajectory and implications.",
        "watch_person": "Demis Hassabis",
        "is_leader_watch": True,
        "content_type": "podcast",
        "source_tier": 1,
    }
    result = enrich_with_signal(item)
    assert result["signal_interview"] is True
    assert result["signal_vector"]["expert_influence"] >= 8
    assert result["signal_score"] >= 65


def test_signal_class_boundaries():
    assert classify_signal(80) == "very_high"
    assert classify_signal(65) == "high"
    assert classify_signal(50) == "medium"
    assert classify_signal(35) == "low"
    assert calculate_signal_score({key: 10 for key in [
        "freshness", "novelty", "future_impact", "technical_significance",
        "strategic_relevance", "expert_influence", "evidence_strength",
        "trend_alignment", "source_quality"
    ]}) == 100.0
