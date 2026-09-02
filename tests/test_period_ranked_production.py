from period_ranked_pipeline import _global_ranked_selection


def test_global_selection_assigns_ranks_to_candidate_window():
    items = [
        {"title": "A", "editorial_score": 110, "source": "source-a", "content_type": "research"},
        {"title": "B", "editorial_score": 108, "source": "source-b", "content_type": "news"},
        {"title": "C", "editorial_score": 106, "source": "source-c", "content_type": "research"},
        {"title": "D", "editorial_score": 104, "source": "source-d", "content_type": "news"},
        {"title": "E", "editorial_score": 102, "source": "source-e", "content_type": "product_news"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    assert [x["period_rank"] for x in ranked] == list(range(1, len(ranked) + 1))
    assert len(ranked) <= 6
    assert [x["final_editorial_score"] for x in ranked] == [82.5, 81.0, 79.5, 78.0, 76.5]
    assert all(x["publication_rank_assigned"] for x in ranked)


def test_protected_flag_does_not_reserve_publication_slot():
    items = [
        {"title": "routine leader story", "editorial_score": 80, "leader_watch_protected": True},
        {"title": "strategic story", "editorial_score": 120, "source": "source-a"},
        {"title": "second strategic story", "editorial_score": 115, "source": "source-b"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    assert ranked[0]["title"] == "strategic story"
    assert ranked[0]["period_rank"] == 1


def test_tier0_keeps_best_story_per_leader():
    items = [
        {"title": "Sam Altman interview: AI future", "summary": "Sam Altman discusses model progress, agents and long-term AI development.", "content_type": "interview", "editorial_score": 95, "source": "source-a", "leader": "Sam Altman", "protected_slot": True},
        {"title": "Sam Altman interview: enterprise AI", "summary": "Sam Altman discusses enterprise deployment, model economics and safety tradeoffs.", "content_type": "interview", "editorial_score": 130, "source": "source-b", "leader": "Sam Altman", "protected_slot": True},
        {"title": "Dario Amodei interview: AI safety", "summary": "Dario Amodei discusses AI safety, capability evaluation and frontier-model risks.", "content_type": "interview", "editorial_score": 120, "source": "source-c", "leader": "Dario Amodei", "protected_slot": True},
        {"title": "normal news", "editorial_score": 110, "source": "source-d", "content_type": "news"},
        {"title": "normal news 2", "editorial_score": 105, "source": "source-e", "content_type": "research"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    tier0 = [x for x in ranked if x.get("tier0_rank") is not None]
    assert [x["title"] for x in tier0] == ["Sam Altman interview: enterprise AI", "Dario Amodei interview: AI safety"]
    assert all(x.get("protected_slot") for x in tier0)


def test_tier0_leader_story_is_not_replaced_by_lower_scoring_same_person():
    items = [
        {"title": "Elon Musk interview high value", "summary": "Elon Musk discusses AI, robotics, autonomy and implications for the future.", "content_type": "interview", "editorial_score": 125, "source": "source-a", "leader": "Elon Musk", "protected_slot": True},
        {"title": "Elon Musk interview lower value", "summary": "Elon Musk discusses a smaller product announcement and short-term roadmap details.", "content_type": "interview", "editorial_score": 80, "source": "source-b", "leader": "Elon Musk", "protected_slot": True},
        {"title": "major research", "editorial_score": 115, "source": "source-c", "content_type": "research"},
    ]
    ranked = _global_ranked_selection(items, 4, 2, 2, {})
    tier0 = [x for x in ranked if x.get("tier0_rank") is not None]
    assert len(tier0) == 1
    assert tier0[0]["title"] == "Elon Musk interview high value"
    assert tier0[0].get("protected_slot") is True
    assert "Elon Musk interview lower value" not in [x["title"] for x in tier0]
