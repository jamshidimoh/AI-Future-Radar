from src.protected_editorial_lane import MIND_IDEAS_VOICES_SCORE_FLOOR, choose_additive_candidates, is_mind_ideas_voices_candidate, mind_ideas_voices_score


def test_mind_candidate_detects_consciousness_content():
    item = {"title": "Artificial consciousness and AI", "mission_area": "mind_cognition", "content_type": "article"}
    assert is_mind_ideas_voices_candidate(item)


def test_podcast_candidate_detects_specialist_format():
    item = {"title": "AI and the mind", "mission_area": "ai_core", "content_type": "podcast"}
    assert is_mind_ideas_voices_candidate(item)


def test_registry_person_candidate_detects_influential_thinker():
    item = {"title": "Yuval Noah Harari on AI and civilization", "mission_area": "future_governance", "content_type": "interview"}
    assert is_mind_ideas_voices_candidate(item)


def test_neuroscience_genetics_and_future_signals_are_eligible():
    for title in (
        "AI, predictive processing and neuroscience",
        "Genomics and AI-driven biology",
        "Scientific foresight on AI and civilization",
        "Technology and society in the age of AI",
    ):
        item = {"title": title, "mission_area": "convergence", "content_type": "article"}
        assert is_mind_ideas_voices_candidate(item)


def test_community_source_is_excluded():
    item = {"title": "Consciousness discussion", "mission_area": "mind_cognition", "content_type": "podcast", "source": "Reddit"}
    assert not is_mind_ideas_voices_candidate(item)


def test_mind_lane_has_independent_quality_floor_but_not_normal_floor():
    strong = {"title": "Consciousness and cognition in AI", "mission_area": "mind_cognition", "content_type": "article", "final_editorial_score": 41.0}
    weak_mind = {"title": "General future discussion", "mission_area": "convergence", "content_type": "article", "source_tier": 3, "final_editorial_score": 80.0}
    strong_score = mind_ideas_voices_score(strong)
    weak_score = mind_ideas_voices_score(weak_mind)
    assert strong_score >= MIND_IDEAS_VOICES_SCORE_FLOOR
    assert strong["final_editorial_score"] < 55.0
    assert weak_score < MIND_IDEAS_VOICES_SCORE_FLOOR
    selected = choose_additive_candidates([strong, weak_mind], existing_ids=set(), max_rank=12, max_items=2)
    assert [item["title"] for item in selected] == [strong["title"]]

def test_mind_lane_has_no_normal_score_floor():
    candidates = [
        {"title": "Low score but strong consciousness relevance", "mission_area": "mind_cognition", "content_type": "article", "source_tier": 3, "final_editorial_score": 41.0},
        {"title": "Higher score but weaker lane relevance", "mission_area": "ai_core", "content_type": "article", "final_editorial_score": 80.0},
    ]
    selected = choose_additive_candidates(candidates, existing_ids=set(), max_items=1)
    assert selected[0]["title"] == "Low score but strong consciousness relevance"
    assert selected[0]["mind_editorial_score"] > 0
    assert selected[0]["normal_period_rank"] is None
    assert selected[0]["mind_lane_selected"] is True


def test_additive_candidates_use_independent_lane_score_and_two_item_cap():
    candidates = [
        {"title": "A consciousness research", "mission_area": "mind_cognition", "content_type": "article", "normal_period_rank": 4, "final_editorial_score": 60.1},
        {"title": "B future governance interview", "mission_area": "future_governance", "content_type": "interview", "source_tier": 1, "normal_period_rank": 5, "final_editorial_score": 56.0},
        {"title": "D cognition podcast", "mission_area": "mind_cognition", "content_type": "podcast", "normal_period_rank": 7, "final_editorial_score": 55.8},
    ]
    selected = choose_additive_candidates(candidates, existing_ids=set(), max_rank=7, max_items=2)
    assert len(selected) == 2
    assert selected[0].get("mind_editorial_score", 0) >= selected[1].get("mind_editorial_score", 0)
    assert all(item.get("mind_lane_selected") for item in selected)


def test_mind_lane_rejects_generic_forum_interview_without_mind_signal():
    item = {
        "title": "Sustainable Development Impact Meetings 2025",
        "mission_area": "ai_core",
        "content_type": "interview",
        "source": "World Economic Forum",
        "source_type": "global_forum",
        "source_tier": 1,
    }
    assert not is_mind_ideas_voices_candidate(item)
