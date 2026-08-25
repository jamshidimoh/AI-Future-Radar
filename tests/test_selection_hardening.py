from src.semantic_threshold import semantic_threshold


def test_adaptive_thresholds_reflect_context():
    assert semantic_threshold({"content_type": "news"}) == 0.62
    assert semantic_threshold({"content_type": "research"}) == 0.64
    assert semantic_threshold({"leader": "AI leader"}) == 0.66
    assert semantic_threshold({"breaking_signal": True}) == 0.72
    assert semantic_threshold({"breaking_signal": True}, local=True) == 0.70
