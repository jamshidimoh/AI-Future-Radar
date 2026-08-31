from src.unified_editorial_selection import (
    assert_portfolio_contract,
    load_editorial_contract,
    select_regular_portfolio,
)


def item(title, source, score, *, area="ai", content_type="news", tier=1, research_signal=False):
    return {
        "title": title,
        "source": source,
        "source_tier": tier,
        "category": area,
        "content_type": content_type,
        "final_editorial_score": score,
        "research_signal": research_signal,
    }


def test_distinct_sources_are_preferred_before_source_repeat():
    candidates = [
        item("OpenAI A", "OpenAI", 100, area="ai"),
        item("OpenAI B", "OpenAI", 99, area="ai"),
        item("MIT A", "MIT CSAIL", 92, area="convergence"),
        item("Nature A", "Nature", 90, area="mind"),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=4,
        max_per_source=2,
        max_per_type=4,
        recent_source_counts={},
    )
    sources = [x["source"] for x in selected]
    assert set(sources[:3]) == {"OpenAI", "MIT CSAIL", "Nature"}
    assert sources.count("OpenAI") <= 2
    assert len(selected) == 4
    assert selected[-1]["mission_selection_reason"] == "adaptive_source_backfill"


def test_recent_source_history_is_preference_not_exclusion():
    candidates = [
        item("OpenAI A", "OpenAI", 100, area="ai"),
        item("MIT A", "MIT CSAIL", 95, area="convergence"),
        item("Nature A", "Nature", 90, area="mind"),
        item("Anthropic A", "Anthropic", 80, area="future"),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=4,
        max_per_source=2,
        max_per_type=4,
        recent_source_counts={"OpenAI": 10, "MIT CSAIL": 0, "Nature": 0, "Anthropic": 0},
    )
    assert any(x["source"] == "OpenAI" for x in selected)
    assert len(selected) == 4


def test_community_sources_are_excluded_from_normal_portfolio():
    candidates = [
        item("Reddit story", "Reddit - r/artificial", 120, tier=3),
        item("MIT story", "MIT CSAIL", 90, area="convergence"),
        item("Nature story", "Nature", 80, area="mind"),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=4,
        max_per_source=2,
        max_per_type=4,
        recent_source_counts={},
    )
    assert all("reddit" not in x["source"].casefold() for x in selected)


def test_mission_targets_are_loaded_from_canonical_policy():
    contract = load_editorial_contract()
    assert contract["max_posts"] == 3
    assert contract["ai_core_target_min"] == 1
    assert contract["ai_core_target_max"] == 2
    assert contract["convergence_target"] == 1
    assert contract["mind_future_target"] == 1
    assert contract["research_target"] == 1
    assert contract["interview_target_max"] == 1
    assert contract["min_authoritative_items"] == 2


def test_mind_future_target_is_one_shared_allocation_not_two_slots():
    candidates = [
        item("Core research", "Nature", 100, area="ai", content_type="research", research_signal=True),
        item("Quantum", "IBM Research", 90, area="quantum", content_type="research", research_signal=True),
        item("Mind", "Stanford HAI", 80, area="mind"),
        item("Future", "NIST", 79, area="future"),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        mission_aware=True,
        strict_relevance=True,
    )
    assert len(selected) == 3
    areas = [x["mission_area"] for x in selected]
    assert "ai_core" in areas
    assert "convergence" in areas
    assert sum(area in {"mind_cognition", "future_governance"} for area in areas) == 1


def test_min_authoritative_items_is_repaired_when_feasible():
    candidates = [
        item("AI unknown tier", "Independent Lab", 100, area="ai", tier=None),
        item("Quantum authoritative", "IBM Research", 90, area="quantum", tier=1),
        item("Future unknown tier", "Independent Policy Lab", 80, area="future", tier=None),
        item("AI authoritative research", "Nature", 70, area="ai", content_type="research", tier=1, research_signal=True),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        mission_aware=True,
        strict_relevance=True,
    )
    assert sum(x.get("source_tier") in {1, 2} for x in selected) >= 2
    assert any(x["source"] == "Nature" for x in selected)
    assert_portfolio_contract(selected)


def test_content_type_and_source_hard_caps_are_enforced():
    candidates = [
        item("A1", "OpenAI", 100, area="ai", content_type="news"),
        item("A2", "OpenAI", 99, area="convergence", content_type="news"),
        item("A3", "OpenAI", 98, area="mind", content_type="news"),
        item("B1", "Nature", 97, area="future", content_type="research"),
        item("C1", "MIT", 96, area="ai", content_type="research"),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=5,
        max_per_source=2,
        max_per_type=2,
        recent_source_counts={},
    )
    counts = {}
    types = {}
    for x in selected:
        counts[x["source"]] = counts.get(x["source"], 0) + 1
        types[x["content_type"]] = types.get(x["content_type"], 0) + 1
    assert max(counts.values()) <= 2
    assert max(types.values()) <= 2


def test_contract_exposes_replacement_window_and_hard_ceiling():
    contract = load_editorial_contract()
    assert contract["candidate_window"] == 6
    assert contract["replacement_buffer"] == 2
    assert contract["preferred_max_same_source"] == 1
    assert contract["hard_max_same_source"] == 2
