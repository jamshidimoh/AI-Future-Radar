from src.mind_cognition_lane import apply_mind_cognition_floor, prepare_mind_cognition_contract
from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio


def _item(title, source, score, area, content_type="research"):
    return {
        "title": title,
        "summary": title,
        "source": source,
        "source_tier": 1,
        "final_editorial_score": score,
        "category": area,
        "content_type": content_type,
        "research_signal": content_type == "research",
        "_ai_link": True,
        "ai_relevance": True,
    }


def test_independent_mind_cognition_target_is_minimum_two():
    contract = load_editorial_contract()
    items = [_item("Mind one", "Nature", 49, "mind"), _item("Mind two", "Aeon", 45, "mind")]
    prepare_mind_cognition_contract(items, contract)
    assert contract["mind_cognition_target"] == 2
    assert contract["mind_cognition_score_floor"] == 50.0
    assert contract["mind_cognition_min_publish"] == 2


def test_mind_candidates_below_fifty_keep_original_score_and_get_bounded_bypass():
    item = _item("Consciousness research", "Nature", 47.25, "mind")
    apply_mind_cognition_floor(item)
    assert item["mind_cognition_original_score"] == 47.25
    assert item["mind_cognition_floor"] == 50.0
    assert item["mind_cognition_floor_bypass"] is True
    assert item["final_editorial_score"] >= 55.0


def test_three_slot_portfolio_prefers_ai_convergence_and_mind_cognition():
    candidates = [
        _item("Frontier AI capability", "OpenAI", 100, "ai"),
        _item("Quantum computing breakthrough for AI", "Nature", 91, "quantum"),
        _item("Consciousness and AI cognition research", "Nature Neuroscience", 88, "mind"),
        _item("Strong future governance analysis", "NIST", 99, "future", "news"),
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
    assert [item["mission_area"] for item in selected] == ["ai_core", "convergence", "mind_cognition"]
