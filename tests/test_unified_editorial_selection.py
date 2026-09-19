from pathlib import Path

import yaml

from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio

ROOT = Path(__file__).resolve().parents[1]


def _load(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def item(title, source, score, area="ai", tier=1, content_type="news", research_signal=False):
    return {
        "title": title,
        "summary": title,
        "source": source,
        "source_tier": tier,
        "final_editorial_score": score,
        "category": area,
        "content_type": content_type,
        "research_signal": research_signal,
        "_ai_link": True,
        "ai_relevance": True,
    }


def test_mission_diversity_is_explicit_and_canonical():
    contract = _load("config/production_contract.yaml")["mission"]
    mission = _load("config/mission_policy.yaml")["mission"]
    selection = _load("config/selection_policy.yaml")["selection"]
    assert set(contract["supported_areas"]) == {
        "ai_core", "convergence", "mind_cognition", "future_governance"
    }
    assert contract["min_unique_sources"] == mission["min_unique_sources"]
    assert contract["preferred_max_same_source_per_run"] == mission["max_same_source"]
    assert contract["hard_max_same_source_per_run"] == selection["max_items_per_source"]
    assert contract["max_same_mission_area_per_run"] == mission["max_same_mission_area"] == 2


def test_mission_coverage_targets_are_explicit_opportunities():
    contract = load_editorial_contract()
    assert contract["max_posts"] == 3
    assert contract["ai_core_target_min"] == 1
    assert contract["ai_core_target_max"] == 2
    assert contract["convergence_target"] == 1
    assert contract["mind_cognition_target"] == 1
    assert contract["mind_future_target"] == 1
    assert contract["research_target"] == 0
    assert contract["interview_target_max"] == 1
    assert contract["min_authoritative_items"] == 2
    assert contract["diversity_weight"] == 8.0
    assert contract["similarity_penalty"] == 12.0


def test_mind_future_target_selects_an_eligible_mind_or_future_item():
    candidates = [
        item("Exceptional AI capability", "OpenAI", 100, area="ai"),
        item("Second exceptional AI capability", "Anthropic", 99, area="ai"),
        item("Strong consciousness research linked to AI", "Nature", 72, area="mind", content_type="research", research_signal=True),
        item("Weak future commentary", "NIST", 35, area="future"),
    ]
    contract = load_editorial_contract()
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 1
    selected = select_regular_portfolio(candidates, max_posts=3, max_per_source=1, max_per_type=3, recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True)
    titles = [x["title"] for x in selected]
    assert "Strong consciousness research linked to AI" in titles
    assert any(x["mission_selection_reason"] == "mission_target:mind_cognition" for x in selected)


def test_zero_mind_future_target_does_not_force_weak_mind_content():
    candidates = [
        item("Exceptional AI capability", "OpenAI", 100, area="ai"),
        item("Second exceptional AI capability", "Anthropic", 99, area="ai"),
        item("Weak mind item", "Stanford HAI", 30, area="mind"),
    ]
    contract = load_editorial_contract()
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    selected = select_regular_portfolio(candidates, max_posts=2, max_per_source=1, max_per_type=2, recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True)
    assert [x["title"] for x in selected] == ["Exceptional AI capability", "Second exceptional AI capability"]


def test_high_value_convergence_can_win_on_score_without_a_mandatory_slot():
    candidates = [
        item("AI core", "OpenAI", 100, area="ai"), item("Transformative robotics breakthrough", "MIT CSAIL", 96, area="robotics", content_type="research", research_signal=True),
        item("AI core second", "Anthropic", 95, area="ai"), item("Weak policy commentary", "NIST", 40, area="future"),
    ]
    contract = load_editorial_contract()
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    selected = select_regular_portfolio(candidates, max_posts=3, max_per_source=1, max_per_type=3, recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True)
    titles = [x["title"] for x in selected]
    assert "Transformative robotics breakthrough" in titles
    assert "Weak policy commentary" not in titles


def test_editorial_contract_loads_rotation_window_from_mission_policy():
    mission = _load("config/mission_policy.yaml")["mission"]
    rotation = _load("config/mission_policy.yaml")["rotation"]
    contract = load_editorial_contract()
    assert contract["window_runs"] == rotation["window_runs"]
    assert contract["max_same_source_in_window"] == rotation["max_same_source_in_window"]
    assert contract["max_same_area_in_window"] == rotation["max_same_area_in_window"]
    assert mission["max_same_source"] <= rotation["max_same_source_in_window"]


def test_window_source_cap_blocks_a_dominant_source_when_an_alternative_exists():
    candidates = [
        item("Repeat source pick 1", "MarkTechPost", 100, area="ai"),
        item("Repeat source pick 2", "MarkTechPost", 99, area="ai"),
        item("Repeat source pick 3", "MarkTechPost", 98, area="ai"),
        item("Fresh alternative source", "Ars Technica", 90, area="ai"),
    ]
    contract = load_editorial_contract()
    contract["convergence_target"] = contract["mind_cognition_target"] = contract["mind_future_target"] = contract["research_target"] = 0
    contract["ai_core_target_min"] = 0
    # MarkTechPost already hit its cross-run cap over the last window.
    selected = select_regular_portfolio(
        candidates, max_posts=1, max_per_source=2, max_per_type=3,
        recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True,
        window_source_counts={"marktechpost": contract["max_same_source_in_window"]}, window_area_counts={},
    )
    assert [x["title"] for x in selected] == ["Fresh alternative source"]


def test_window_source_cap_is_bypassed_rather_than_publishing_nothing():
    candidates = [
        item("Only available source pick 1", "MarkTechPost", 100, area="ai"),
        item("Only available source pick 2", "MarkTechPost", 99, area="ai"),
    ]
    contract = load_editorial_contract()
    contract["convergence_target"] = contract["mind_cognition_target"] = contract["mind_future_target"] = contract["research_target"] = 0
    contract["ai_core_target_min"] = 0
    # Every candidate is from a source already at its window cap; the run must
    # still publish rather than yield zero items.
    selected = select_regular_portfolio(
        candidates, max_posts=1, max_per_source=2, max_per_type=3,
        recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True,
        window_source_counts={"marktechpost": contract["max_same_source_in_window"]}, window_area_counts={},
    )
    assert len(selected) == 1
    assert selected[0]["source"] == "MarkTechPost"


def test_window_area_cap_prefers_an_underrepresented_area():
    candidates = [
        item("AI core pick", "OpenAI", 100, area="ai"),
        item("Second AI core pick", "Anthropic", 95, area="ai"),
        item("Convergence pick", "MIT CSAIL", 80, area="robotics", content_type="research", research_signal=True),
    ]
    contract = load_editorial_contract()
    contract["convergence_target"] = contract["mind_cognition_target"] = contract["mind_future_target"] = contract["research_target"] = 0
    contract["ai_core_target_min"] = 0
    contract["ai_core_target_max"] = 2
    selected = select_regular_portfolio(
        candidates, max_posts=3, max_per_source=1, max_per_type=3,
        recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True,
        window_source_counts={}, window_area_counts={"ai_core": contract["max_same_area_in_window"]},
    )
    titles = [x["title"] for x in selected]
    assert "Convergence pick" in titles
    assert len(titles) <= 2


def test_authority_repair_preserves_mission_target_over_generic_candidate():
    candidates = [
        item("Authoritative AI story", "OpenAI", 100, area="ai", tier=1),
        item("Mission convergence target", "Scientific outlet", 82, area="robotics", tier=3, content_type="research", research_signal=True),
        item("Generic low-authority story", "Generic outlet", 75, area="ai", tier=3),
        item("Authoritative replacement", "Nature", 72, area="ai", tier=1),
    ]
    contract = load_editorial_contract()
    contract["ai_core_target_min"] = 1
    contract["convergence_target"] = 1
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0
    selected = select_regular_portfolio(
        candidates,
        max_posts=3,
        max_per_source=2,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    titles = [x["title"] for x in selected]
    assert "Mission convergence target" in titles
    assert "Authoritative replacement" in titles
    assert "Generic low-authority story" not in titles
