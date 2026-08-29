from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio


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
        item("OpenAI A", "OpenAI", 100),
        item("OpenAI B", "OpenAI", 99),
        item("MIT A", "MIT CSAIL", 92),
        item("Nature A", "Nature", 90),
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
        item("OpenAI A", "OpenAI", 100),
        item("MIT A", "MIT CSAIL", 95),
        item("Nature A", "Nature", 90),
        item("Anthropic A", "Anthropic", 80),
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
        item("MIT story", "MIT CSAIL", 90),
        item("Nature story", "Nature", 80),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=4,
        max_per_source=2,
        max_per_type=4,
        recent_source_counts={},
    )
    assert all("reddit" not in x["source"].casefold() for x in selected)


def test_mission_coverage_gets_explicit_opportunities():
    candidates = [
        item("AI core", "OpenAI", 100, area="ai"),
        item("Quantum", "IBM Quantum", 82, area="quantum"),
        item("Mind", "Stanford HAI", 80, area="mind"),
        item("Future", "NIST", 78, area="future"),
        item("Research", "Nature", 77, area="ai", content_type="research", research_signal=True),
    ]
    selected = select_regular_portfolio(
        candidates,
        max_posts=4,
        max_per_source=2,
        max_per_type=4,
        recent_source_counts={},
    )
    reasons = {x.get("mission_selection_reason") for x in selected}
    assert "mission_coverage:convergence" in reasons
    assert "mission_coverage:mind_cognition" in reasons
    assert "mission_coverage:future_governance" in reasons
    assert len(selected) == 4


def test_content_type_and_source_hard_caps_are_enforced():
    candidates = [
        item("A1", "OpenAI", 100, content_type="news"),
        item("A2", "OpenAI", 99, content_type="news"),
        item("A3", "OpenAI", 98, content_type="news"),
        item("B1", "Nature", 97, content_type="research"),
        item("C1", "MIT", 96, content_type="research"),
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
    assert contract["max_posts"] == 4
    assert contract["candidate_window"] == 6
    assert contract["replacement_buffer"] == 2
    assert contract["preferred_max_same_source"] == 1
    assert contract["hard_max_same_source"] == 2
