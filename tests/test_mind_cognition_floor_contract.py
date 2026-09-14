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


def test_mind_cognition_has_independent_contract_floor():
    contract = load_editorial_contract()
    assert contract["mind_cognition_target"] >= 1


def test_three_slot_portfolio_cannot_starve_mind_for_future_governance():
    candidates = [
        _item("Frontier AI capability", "OpenAI", 100, "ai"),
        _item("Quantum computing breakthrough for AI", "Nature", 91, "quantum"),
        _item("Consciousness and AI cognition research", "Nature Neuroscience", 88, "mind"),
        _item("Philosophy of science and AI discovery", "Stanford Encyclopedia of Philosophy", 86, "mind"),
        _item("Strong future governance analysis", "NIST", 99, "future", "news"),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=1,
        max_per_type=2,
        recent_source_counts={},
        contract=load_editorial_contract(),
        mission_aware=True,
        strict_relevance=True,
    )
    areas = [item["mission_area"] for item in selected]
    assert areas == ["ai_core", "convergence", "mind_cognition"]
