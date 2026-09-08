from src.semantic_threshold import semantic_threshold


def test_adaptive_thresholds_reflect_context():
    assert semantic_threshold({"content_type": "news"}) == 0.68
    assert semantic_threshold({"content_type": "research"}) == 0.68
    assert semantic_threshold({"leader": "AI leader"}) == 0.70
    assert semantic_threshold({"breaking_signal": True}) == 0.74
    assert semantic_threshold({"breaking_signal": True}, local=True) == 0.72
