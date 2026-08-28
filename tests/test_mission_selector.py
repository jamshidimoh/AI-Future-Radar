import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mission_selector import classify_area, select_mission_portfolio


def test_mission_portfolio_covers_multiple_frontiers():
    items = [
        {"title": "New reasoning model reaches frontier benchmark", "summary": "A new AI model improves reasoning and agentic capability.", "source": "OpenAI", "source_tier": 1, "content_type": "official", "editorial_score": 30},
        {"title": "Nature study demonstrates new protein design method with AI", "summary": "Researchers use machine learning for protein design.", "source": "Nature", "source_tier": 1, "content_type": "research", "editorial_score": 28},
        {"title": "Quantum processor enables new hybrid AI experiment", "summary": "Researchers connect quantum computing and machine learning.", "source": "IBM Research", "source_tier": 1, "content_type": "research", "editorial_score": 27},
        {"title": "Scientists debate machine consciousness and sentience", "summary": "A cognitive science discussion examines consciousness in artificial systems.", "source": "MIT", "source_tier": 1, "content_type": "talk", "editorial_score": 25},
        {"title": "New AI benchmark released", "summary": "A new benchmark measures model capabilities.", "source": "Stanford HAI", "source_tier": 1, "content_type": "research", "editorial_score": 20},
    ]
    result = select_mission_portfolio(items, max_posts=4)
    assert len(result) == 4
    assert len({x["source"] for x in result}) == 4
    areas = {x["mission_area"] for x in result}
    assert "convergence" in areas
    assert "mind_cognition" in areas
    assert "ai_core" in areas or "future_governance" in areas


def test_low_signal_roundup_is_rejected():
    items = [
        {"title": "Top 10 AI tools", "summary": "Best tools and prompt collection.", "source": "Community", "source_tier": 3, "content_type": "news", "editorial_score": 50},
        {"title": "MIT research reveals new agent capability", "summary": "A new research result changes the frontier for AI agents.", "source": "MIT News", "source_tier": 1, "content_type": "research", "editorial_score": 20},
    ]
    result = select_mission_portfolio(items, max_posts=4)
    assert len(result) == 1
    assert result[0]["source"] == "MIT News"


def test_unknown_publisher_cannot_become_regular_top_story_by_keyword_boost():
    items = [
        {
            "title": "AI breakthrough new model roadmap investment frontier",
            "summary": "A new AI capability and investment roadmap is announced.",
            "source": "Example Finance Blog",
            "content_type": "news",
            "editorial_score": 50,
        },
        {
            "title": "Reuters reports new AI capability",
            "summary": "A major AI development is reported with evidence and context.",
            "source": "Reuters",
            "content_type": "news",
            "editorial_score": 25,
        },
    ]
    result = select_mission_portfolio(items, max_posts=4)
    assert result
    assert result[0]["source"] == "Reuters"
    assert all(x["source"] != "Example Finance Blog" for x in result)


def test_authoritative_technology_media_remains_eligible():
    items = [
        {
            "title": "TechCrunch reports new agentic AI deployment",
            "summary": "The deployment demonstrates a new capability with concrete evidence.",
            "source": "TechCrunch",
            "content_type": "news",
            "editorial_score": 25,
        }
    ]
    result = select_mission_portfolio(items, max_posts=4)
    assert len(result) == 1
    assert result[0]["source"] == "TechCrunch"
    assert result[0]["source_tier_effective"] == 2


def test_routine_chatgpt_application_is_not_top_story_without_strong_signal():
    items = [
        {
            "title": "Build a personalized meal planner with ChatGPT Workflows",
            "summary": "A practical workflow shows how ChatGPT can plan meals and save time.",
            "source": "OpenAI",
            "source_tier": 1,
            "content_type": "official",
            "editorial_score": 40,
        },
        {
            "title": "New multimodal AI capability reaches frontier benchmark",
            "summary": "Researchers demonstrate a new model capability with measured gains.",
            "source": "DeepMind",
            "source_tier": 1,
            "content_type": "research",
            "editorial_score": 30,
        },
    ]
    result = select_mission_portfolio(items, max_posts=2)
    assert result
    assert result[0]["source"] == "DeepMind"
    assert all("meal planner" not in x["title"].lower() for x in result)


def test_routine_chatgpt_application_is_blocked_without_strong_signal_even_with_high_editorial_score():
    items = [
        {
            "title": "Build a personalized meal planner with ChatGPT Workflows",
            "summary": "A practical workflow shows how ChatGPT can plan meals and save time.",
            "source": "OpenAI",
            "source_tier": 1,
            "content_type": "official",
            "editorial_score": 95,
        }
    ]
    result = select_mission_portfolio(items, max_posts=1)
    assert result == []


def test_routine_application_with_explicit_frontier_signal_remains_eligible():
    items = [
        {
            "title": "New agentic architecture enables autonomous meal planning research",
            "summary": "Researchers demonstrate a new architecture and frontier capability.",
            "source": "DeepMind",
            "source_tier": 1,
            "content_type": "research",
            "editorial_score": 20,
            "breakthrough_signal": True,
        }
    ]
    result = select_mission_portfolio(items, max_posts=1)
    assert len(result) == 1
    assert result[0]["routine_application_strong_signal"] is True


def test_area_classification_maps_quantum_to_convergence():
    assert classify_area({"title": "Quantum computing for machine learning"}) == "convergence"
