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


def test_publication_summary_budget_keeps_independent_mind_items_outside_protected_floor():
    selected = [
        {"title": "normal-1", "normal_period_rank": 1, "final_editorial_score": 60.0},
        {
            "title": "mind-low-score",
            "normal_period_rank": None,
            "final_editorial_score": 50.0,
            "protected_content": True,
            "protected_editorial_lane": "mind_ideas_voices",
            "mind_lane_selected": True,
            "mind_editorial_score": 77.0,
        },
    ]

    bounded = _publication_summary_budget(selected, max_posts=1, policy={})
    assert [item["title"] for item in bounded] == ["normal-1", "mind-low-score"]


def test_publication_summary_budget_preserves_technical_mind_and_voice_lanes():
    selected = [
        {"title": "normal-1", "normal_period_rank": 1},
        {"title": "technical", "technical_trend_lane_selected": True, "technical_trend_period_rank": 1},
        {"title": "mind", "mind_lane_selected": True, "mind_period_rank": 1, "mind_editorial_score": 70.0},
        {"title": "voice", "voices_perspectives_lane_selected": True, "voices_period_rank": 1, "voices_perspectives_score": 90.0},
    ]
    bounded = _publication_summary_budget(selected, max_posts=1, policy={})
    assert [item["title"] for item in bounded] == ["normal-1", "technical", "mind", "voice"]
