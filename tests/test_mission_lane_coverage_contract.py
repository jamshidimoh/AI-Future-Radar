from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio


def _item(title, source, score, category, content_type="research"):
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


def test_production_contract_requires_core_mission_lanes_when_candidates_exist():
    contract = load_editorial_contract()
    assert contract["ai_core_target_min"] >= 1
    assert contract["convergence_target"] >= 1
    assert contract["mind_cognition_target"] >= 1
    assert contract["max_same_mission_area"] <= 2
    assert contract["max_items_per_content_type"] >= 2


def test_three_slot_portfolio_prefers_ai_convergence_and_mind_over_ai_only():
    candidates = [
        _item("Frontier AI capability", "OpenAI", 100, "ai"),
        _item("Second frontier AI capability", "Anthropic", 99, "ai"),
        _item("Quantum computing breakthrough for AI", "Nature", 91, "quantum"),
        _item("Consciousness and AI cognition research", "Nature Neuroscience", 88, "mind"),
        _item("Philosophy of science and AI discovery", "Stanford Encyclopedia of Philosophy", 86, "mind"),
        _item("Weak generic AI governance commentary", "NIST", 65, "future", "news"),
    ]
    contract = load_editorial_contract()
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=1,
        max_per_type=2,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    areas = [item["mission_area"] for item in selected]
    assert "ai_core" in areas
    assert "convergence" in areas
    assert "mind_cognition" in areas
    assert len(selected) == 3
