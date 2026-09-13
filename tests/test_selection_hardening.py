from src.semantic_threshold import semantic_threshold


def test_adaptive_thresholds_reflect_context():
    assert semantic_threshold({"content_type": "news"}) == 0.90
    assert semantic_threshold({"content_type": "research"}) == 0.89
    assert semantic_threshold({"leader": "AI leader"}) == 0.88
    assert semantic_threshold({"breaking_signal": True}) == 0.86
    assert semantic_threshold({"breaking_signal": True}, local=True) == 0.84
