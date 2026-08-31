from src.unified_editorial_selection import select_regular_portfolio


def test_strict_relevance_removes_unclassified_candidates():
    candidates = [
        {"title": "Unrelated sports headline", "category": "sports", "final_editorial_score": 99},
        {"title": "Quantum hardware result", "category": "quantum", "final_editorial_score": 90},
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=2,
        max_per_type=2,
        strict_relevance=True,
    )
    assert [x["title"] for x in selected] == ["Quantum hardware result"]
