from src.signal_engine import calculate_signal_score, classify_signal, enrich_with_signal


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
    # Interview recognition is metadata; leader authority no longer adds a
    # separate +15 ranking bonus to the technology signal.
    assert result["signal_score"] == 47.95


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
