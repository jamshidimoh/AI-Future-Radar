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
    selected = select_regular_portfolio(candidates, max_posts=3, max_per_source=1, max_per_type=3, recent_source_counts={}, mission_aware=True, strict_relevance=True)
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
    contract["mind_future_target"] = 0
    selected = select_regular_portfolio(candidates, max_posts=3, max_per_source=1, max_per_type=3, recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True)
    titles = [x["title"] for x in selected]
    assert "Transformative robotics breakthrough" in titles
    assert "Weak policy commentary" not in titles
