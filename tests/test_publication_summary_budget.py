from main import _publication_summary_budget


def test_publication_summary_budget_keeps_rank_breadth_without_summarizing_all_ranked_items():
    selected = [
        {"title": "tier0-high", "protected_slot": True, "final_editorial_score": 61.0},
        {"title": "tier0-low", "protected_slot": True, "final_editorial_score": 25.0},
        {"title": "normal-1", "normal_period_rank": 1},
        {"title": "normal-2", "normal_period_rank": 2},
        {"title": "normal-3", "normal_period_rank": 3},
        {"title": "normal-4", "normal_period_rank": 4},
        {"title": "normal-5", "normal_period_rank": 5},
        {"title": "normal-6", "normal_period_rank": 6},
    ]

    bounded = _publication_summary_budget(selected, max_posts=3, policy={})
    titles = [item["title"] for item in bounded]

    assert titles == [
        "tier0-high",
        "normal-1",
        "normal-2",
        "normal-3",
        "normal-4",
        "normal-5",
        "normal-6",
    ]
