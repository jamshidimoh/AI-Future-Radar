from src.unified_editorial_selection import is_mission_relevant, select_regular_portfolio


def test_unrelated_story_is_rejected():
    assert not is_mission_relevant({"title": "Tennis:30", "content_type": "video"})


def test_mission_keyword_is_retained():
    item = {"title": "New multimodal reasoning model", "content_type": "news"}
    assert is_mission_relevant(item)
    assert item["mission_area"] == "ai_core"


def test_selection_uses_replacement_buffer_capacity():
    candidates = [
        {"title": "AI model breakthrough", "source": "A", "content_type": "research", "mission_area": "ai_core", "score": 90},
        {"title": "Quantum AI processor", "source": "B", "content_type": "research", "mission_area": "convergence", "score": 80},
        {"title": "Future of AI governance", "source": "C", "content_type": "policy", "mission_area": "future_governance", "score": 70},
        {"title": "Brain cognition and AI", "source": "D", "content_type": "research", "mission_area": "mind_cognition", "score": 60},
        {"title": "AI deployment", "source": "E", "content_type": "news", "mission_area": "ai_core", "score": 50},
    ]
    selected = select_regular_portfolio(candidates, max_posts=5, max_per_source=2, max_per_type=3, mission_aware=True)
    assert len(selected) >= 4
    assert all(is_mission_relevant(item) for item in selected)
