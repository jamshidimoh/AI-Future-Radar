from src.protected_editorial_lane import (
    choose_additive_candidates,
    is_mind_ideas_voices_candidate,
    mind_ideas_voices_score,
)


def test_mind_lane_does_not_use_normal_score_floor():
    item = {
        "title": "Can AI ever be conscious?",
        "summary": "A specialist discussion about machine consciousness and cognition.",
        "description": "Researchers examine whether consciousness can be meaningfully attributed to artificial systems.",
        "mission_area": "mind_cognition",
        "content_type": "article",
        "source": "Nature",
        "source_type": "scientific",
        "source_tier": 3,
        "editorial_score": 43.0,
    }
    assert is_mind_ideas_voices_candidate(item)
    mind_score = mind_ideas_voices_score(item)
    assert 0.0 <= mind_score <= 100.0
    selected = choose_additive_candidates([item], existing_ids=set(), max_items=2)
    assert selected == [item]
    assert item["mind_period_rank"] == 1
    assert item["protected_editorial_lane"] == "mind_ideas_voices"
    assert item["normal_period_rank"] is None


def test_mind_lane_selects_from_full_pool_not_normal_rank_window():
    normal = {
        "title": "Routine AI tooling release",
        "mission_area": "ai_core",
        "content_type": "news",
        "source": "OpenAI",
        "source_type": "official",
        "source_tier": 1,
        "normal_period_rank": 1,
    }
    mind = {
        "title": "Artificial consciousness and cognitive science",
        "summary": "A specialist analysis of machine consciousness.",
        "mission_area": "mind_cognition",
        "content_type": "article",
        "source": "Nature",
        "source_type": "scientific",
        "source_tier": 2,
        "normal_period_rank": None,
    }
    selected = choose_additive_candidates([normal, mind], existing_ids={id(normal)}, max_items=2)
    assert selected == [mind]
    assert mind["mind_period_rank"] == 1


def test_untrusted_community_sources_are_not_admitted_to_mind_lane():
    item = {
        "title": "Artificial consciousness discussion",
        "mission_area": "mind_cognition",
        "content_type": "article",
        "source": "Community aggregator",
    }
    assert not is_mind_ideas_voices_candidate(item)
