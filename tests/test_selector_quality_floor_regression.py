from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio


def _item(title, source, score, category, content_type="news"):
    return {
        "title": title,
        "summary": title,
        "source": source,
        "source_tier": 1,
        "final_editorial_score": score,
        "category": category,
        "content_type": content_type,
        "research_signal": content_type == "research",
        "_ai_link": True,
        "ai_relevance": True,
    }


def test_weak_future_opportunity_does_not_displace_strong_convergence():
    candidates = [
        _item("Frontier AI capability", "OpenAI", 100, "ai"),
        _item("Second frontier AI capability", "Anthropic", 99, "ai"),
        _item("Robotics breakthrough", "MIT CSAIL", 90, "robotics", "research"),
        _item("Consciousness research", "Nature", 84, "mind", "research"),
        _item("Weak future governance commentary", "NIST", 70, "future"),
    ]
    contract = load_editorial_contract()
    contract["mind_future_target"] = 2
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    areas = [item["mission_area"] for item in selected]
    assert "ai_core" in areas
    assert "convergence" in areas
    assert "mind_cognition" in areas
    assert "future_governance" not in areas
