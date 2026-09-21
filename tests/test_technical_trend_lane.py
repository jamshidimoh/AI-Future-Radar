from src.technical_trend_lane import choose_technical_trend_candidate, is_technical_trend_candidate


def test_top_technical_candidate_only():
    items = [
        {
            "title": "MCP protocol for AI agents",
            "summary": "Model Context Protocol architecture and runtime",
            "source_type": "technical",
            "source_tier": 1,
            "category": "ai",
            "published": "2026-09-15 10:00",
        },
        {
            "title": "General AI news",
            "summary": "A new model was released",
            "source_type": "news",
            "source_tier": 1,
            "category": "ai",
        },
    ]
    selected = choose_technical_trend_candidate(items)
    assert len(selected) == 1
    assert selected[0]["technical_trend_lane_selected"] is True


def test_arxiv_reddit_excluded():
    assert not is_technical_trend_candidate(
        {
            "title": "New transformer architecture",
            "summary": "AI inference architecture benchmark",
            "source": "arXiv",
            "source_type": "research",
            "source_tier": 1,
            "category": "ai",
        }
    )
    assert not is_technical_trend_candidate(
        {
            "title": "AI inference architecture discussion",
            "summary": "runtime and protocol trend",
            "source": "Reddit community",
            "source_type": "technical",
            "source_tier": 1,
            "category": "ai",
        }
    )



def test_frontier_capability_candidate_is_eligible():
    item = {
        "title": "Gemini Robotics 2 introduces a new capability for autonomous action",
        "summary": "A frontier model improves robotics performance on new situations.",
        "source": "Google DeepMind",
        "source_type": "official",
        "source_tier": 1,
        "category": "ai",
    }
    assert is_technical_trend_candidate(item)
    selected = choose_technical_trend_candidate([item])
    assert len(selected) == 1
    assert selected[0]["technical_trend_lane_selected"] is True
