from src.ranking_guard import filter_quality_candidates


def test_low_confidence_item_is_rejected():
    items = [{"title": "weak story", "editorial_score": 1, "editorial_confidence": 0.1}]
    assert filter_quality_candidates(items) == []


def test_leader_content_has_relaxed_gate():
    items = [{"title": "leader interview", "leader": "AI Leader", "editorial_score": 10, "editorial_confidence": 0.5}]
    assert len(filter_quality_candidates(items)) == 1
