from src.content_selector import select_content
from src.semantic_threshold import semantic_threshold


def test_quality_gate_runs_before_selection():
    items = [
        {"title": "weak", "editorial_score": 1, "editorial_confidence": 0.1, "content_type": "news"},
        {"title": "strong", "editorial_score": 10, "editorial_confidence": 0.9, "content_type": "news"},
    ]
    selected = select_content(items, max_posts=1)
    assert [x["title"] for x in selected] == ["strong"]


def test_adaptive_thresholds_reflect_context():
    assert semantic_threshold({"content_type": "news"}) == 0.62
    assert semantic_threshold({"content_type": "research"}) == 0.64
    assert semantic_threshold({"leader": "AI leader"}) == 0.66
    assert semantic_threshold({"breaking_signal": True}) == 0.72
    assert semantic_threshold({"breaking_signal": True}, local=True) == 0.70
