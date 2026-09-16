from src.protected_editorial_lane import choose_additive_candidates, is_mind_ideas_voices_candidate


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


def test_additive_candidates_max_two_and_keep_floor():
    candidates = [
        {"title": "A", "mission_area": "mind_cognition", "content_type": "article", "normal_period_rank": 4, "final_editorial_score": 55.1},
        {"title": "B", "mission_area": "future_governance", "content_type": "interview", "normal_period_rank": 5, "final_editorial_score": 56.0},
        {"title": "C", "mission_area": "mind_cognition", "content_type": "article", "normal_period_rank": 6, "final_editorial_score": 54.9},
    ]
    selected = choose_additive_candidates(candidates, existing_ids=set(), max_rank=6, max_items=2)
    assert selected == [candidates[0], candidates[1]]
    assert len(selected) <= 2
