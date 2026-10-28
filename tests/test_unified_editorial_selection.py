from pathlib import Path

import yaml

import src.unified_editorial_selection as selection_module
from src.unified_editorial_selection import (
    _eligible_candidates,
    _Portfolio,
    _second_ai_consumes_reserved_mission_source,
    candidate_score,
    is_mission_relevant,
    load_editorial_contract,
    mission_area,
    select_regular_portfolio,
    source_key,
)

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


def test_optional_second_ai_preserves_the_only_source_for_mind_target():
    fixture = yaml.safe_load((ROOT / "tests/characterization/select_regular_portfolio.json").read_text(encoding="utf-8"))
    contract = dict(fixture["contract"])
    contract["mind_cognition_target"] = 1
    contract["mind_future_target"] = 0
    eligible = _eligible_candidates(fixture["candidates"], contract, strict_relevance=False)
    by_title = {candidate["title"]: candidate for candidate in eligible}
    ai_first = by_title["Ai Core candidate 0 machine learning"]
    ai_second = by_title["Ai Core candidate 1 machine learning"]
    mind_target = by_title["Mind Cognition candidate 8 machine learning"]

    assert ai_second["source"] == mind_target["source"]
    portfolio = _Portfolio(
        contract=contract,
        limit=3,
        source_cap=1,
        type_cap=1,
        recent={},
        mission_aware=True,
    )
    portfolio.add(ai_first, "test:ai_first")

    assert mission_area(mind_target) == "mind_cognition"
    assert candidate_score(mind_target) > 0
    assert source_key(ai_second) == source_key(mind_target)
    assert portfolio.interview_count == 0
    assert portfolio.admissible(
        mind_target,
        repeat_source=False,
        ignore_type_cap=True,
        ignore_window_cap=True,
        ignore_area_window_cap=True,
    )
    mind_pool = [
        item for item in eligible
        if mission_area(item) == "mind_cognition"
        and id(item) not in portfolio.selected_ids
        and candidate_score(item) >= min(candidate_score(selected) for selected in portfolio.selected) * float(
            contract.get("mission_target_quality_floor_ratio", 0.82) or 0.82
        )
        and candidate_score(item) > 0
        and portfolio.admissible(
            item,
            repeat_source=False,
            ignore_type_cap=True,
            ignore_window_cap=True,
            ignore_area_window_cap=True,
        )
    ]
    assert mind_pool == [mind_target]
    assert _second_ai_consumes_reserved_mission_source(portfolio, eligible, ai_second)


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
    assert contract["max_same_mission_area_per_run"] == mission["max_same_mission_area"] == 8


def test_mission_coverage_targets_are_explicit_opportunities():
    contract = load_editorial_contract()
    assert contract["max_posts"] == 8
    assert contract["ai_core_target_min"] == 1
    assert contract["ai_core_target_max"] == 8
    assert contract["convergence_target"] == 1
    assert contract["mind_cognition_target"] == 1
    assert contract["mind_future_target"] == 1
    assert contract["research_target"] == 0
    assert contract["interview_target_max"] == 2
    assert contract["min_authoritative_items"] == 2
    assert contract["diversity_weight"] == 11.0
    assert contract["similarity_penalty"] == 16.0


def test_mind_future_target_selects_an_eligible_mind_or_future_item():
    candidates = [
        item("Exceptional AI capability", "OpenAI", 100, area="ai"),
        item("Second exceptional AI capability", "Anthropic", 99, area="ai"),
        item("Strong consciousness research linked to AI", "Nature", 90, area="mind", content_type="research", research_signal=True),
        item("Weak future commentary", "NIST", 35, area="future"),
    ]
    contract = load_editorial_contract()
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 1
    selected = select_regular_portfolio(candidates, max_posts=3, max_per_source=1, max_per_type=3, recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True)
    titles = [x["title"] for x in selected]
    assert "Strong consciousness research linked to AI" in titles
    assert "Exceptional AI capability" in titles
    assert "Second exceptional AI capability" in titles
    assert sum(1 for x in selected if x["mission_area"] == "ai_core") == 2
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


def test_gaming_content_is_rejected_even_when_labeled_ai_core():
    candidate = {
        "title": "Battle Drones: بازی استراتژی زمان واقعی با همگام‌سازی صوتی",
        "summary": "A real-time strategy video game with AI-powered matchmaking.",
        "category": "ai",
        "mission_area": "ai_core",
        "content_type": "video game",
        "tags": ["artificial intelligence"],
    }

    from src.unified_editorial_selection import is_mission_relevant

    assert not is_mission_relevant(candidate, strict=True)
    assert candidate["mission_area"] == "excluded_gaming"
    assert candidate["_mission_area_rejected"] == "gaming_content"


def test_game_theory_for_ai_alignment_is_not_gaming_content():
    from src.unified_editorial_selection import _is_gaming_content, is_mission_relevant

    candidate = {
        "title": "Game theory provides a framework for AI alignment research",
        "summary": "Researchers apply game-theoretic models to alignment and strategic cooperation.",
        "category": "ai",
        "mission_area": "ai_core",
        "content_type": "research",
    }

    assert not _is_gaming_content(candidate)
    assert is_mission_relevant(candidate, strict=True)


def test_low_signal_chatgpt_tutorial_is_rejected_even_with_ai_category():
    candidate = item(
        "How to use ChatGPT to identify scam messages",
        "YouTube - OpenAI",
        90,
        area="ai",
    )
    from src.unified_editorial_selection import is_mission_relevant
    assert is_mission_relevant(candidate, strict=True) is False


def test_explicit_ai_core_label_requires_content_evidence():
    candidate = {
        "title": "Plato Matters More Than Ever",
        "summary": "A general discussion of Plato's relevance to classical ethics and political thought.",
        "source": "Big Think",
        "category": "ai",
        "mission_area": "ai_core",
        "content_type": "podcast",
        "watch_person": "Angie Hobbs",
    }

    assert not is_mission_relevant(candidate, strict=True)
    assert candidate["mission_area"] == "unclassified"
    assert candidate["_mission_area_rejected"] == "ai_core_without_content_evidence"


def test_explicit_ai_core_label_accepts_concrete_ai_evidence():
    candidate = {
        "title": "How frontier AI models are changing scientific discovery",
        "summary": "Researchers use large language models to speed up discovery.",
        "source": "MIT Technology Review",
        "mission_area": "ai_core",
    }

    assert is_mission_relevant(candidate, strict=True)
    assert candidate["mission_area"] == "ai_core"


def test_explicit_ai_core_label_is_reclassified_when_content_is_another_mission_area():
    candidate = {
        "title": "A new quantum computing architecture reaches a milestone",
        "summary": "The team reports a quantum computing advance.",
        "source": "Nature",
        "mission_area": "ai_core",
    }

    assert is_mission_relevant(candidate, strict=True)
    assert candidate["mission_area"] == "convergence"


def test_low_signal_chatgpt_tutorial_is_rejected_with_explicit_ai_core_area():
    candidate = item(
        "How to use ChatGPT for productivity",
        "Specialist publication",
        90,
        area="ai",
    )
    candidate["mission_area"] = "ai_core"
    from src.unified_editorial_selection import is_mission_relevant
    assert is_mission_relevant(candidate, strict=True) is False


def test_known_aggregator_is_excluded_from_normal_portfolio():
    candidate = item(
        "AI startup raises major funding",
        "Techmeme",
        95,
        area="ai",
    )
    selected = select_regular_portfolio(
        [candidate],
        max_posts=1,
        max_per_source=1,
        max_per_type=1,
        recent_source_counts={},
        mission_aware=True,
        strict_relevance=True,
    )
    assert selected == []


def test_entity_repetition_is_penalized_when_quality_is_close():
    candidates = [
        item("OpenAI releases a new reasoning model", "OpenAI News", 100, area="ai"),
        item("OpenAI expands reasoning model deployment", "Reuters", 98, area="ai"),
        item("Robotics system learns physical manipulation", "Nature", 94, area="robotics", content_type="research", research_signal=True),
    ]
    contract = load_editorial_contract()
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0
    contract["ai_core_target_min"] = 0
    selected = select_regular_portfolio(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    titles = [x["title"] for x in selected]
    assert "Robotics system learns physical manipulation" in titles
    assert len([t for t in titles if "OpenAI" in t]) == 1


def test_recent_history_saturation_penalizes_same_topic_without_hard_block():
    history = [
        "__semantic_story__:{\"anchors\":[\"openai\",\"ai_agents\"],\"context\":[\"openai\",\"agents\",\"deployment\",\"reasoning\"],\"events\":[\"deployment\"],\"numbers\":[],\"personnel\":[],\"title\":[\"openai\",\"reasoning\"],\"title_text\":\"openai reasoning deployment\"}"
    ]
    candidates = [
        item("OpenAI reasoning deployment expands", "Reuters", 100, area="ai"),
        item("Quantum sensing improves biological measurements", "Nature", 92, area="robotics", content_type="research", research_signal=True),
    ]
    contract = load_editorial_contract()
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0
    contract["ai_core_target_min"] = 0
    selected = select_regular_portfolio(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
        history_signatures=history,
    )
    assert selected[0]["title"] == "Quantum sensing improves biological measurements" or len(selected) == 2


def test_legacy_list_history_signature_is_safe_and_measurable():
    from src.information_gain import editorial_novelty_score

    item_data = item("Robotics reasoning system update", "Nature", 90, area="robotics")
    legacy_history = [["robotics", "reasoning", "system", "update"]]
    result = editorial_novelty_score(item_data, [], legacy_history)
    assert 0.0 <= result["history_topic_similarity"] <= 1.0
    assert result["novelty"] <= 1.0


def test_selection_exposes_history_and_entity_novelty_metrics():
    selected = select_regular_portfolio(
        [
            item("OpenAI model architecture breakthrough", "OpenAI News", 95, area="ai"),
            item("Robotics breakthrough in physical AI", "Nature", 92, area="robotics", content_type="research", research_signal=True),
        ],
        max_posts=2,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=load_editorial_contract(),
        mission_aware=True,
        strict_relevance=True,
        history_signatures=[],
    )
    assert all("current_entity_overlap" in x for x in selected)
    assert all("history_topic_similarity" in x for x in selected)
    assert all("portfolio_information_gain" in x for x in selected)



def test_freshness_is_exposed_and_recent_story_can_outweigh_small_quality_gap():
    from src.unified_editorial_selection import freshness_score

    recent = item("Recent capability update", "Nature", 91, area="convergence", content_type="research", research_signal=True)
    old = item("Older AI capability update", "OpenAI", 96, area="ai")
    recent["published"] = "2026-09-21T18:00:00Z"
    old["published"] = "2026-09-17T18:00:00Z"
    assert freshness_score(recent) > freshness_score(old)
    contract = load_editorial_contract()
    contract.update(convergence_target=0, mind_cognition_target=0, mind_future_target=0, research_target=0, ai_core_target_min=0)
    selected = select_regular_portfolio(
        [old, recent],
        max_posts=1,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    assert selected[0]["title"] == "Recent capability update"
    assert "freshness_score" in selected[0]


def test_mission_target_competes_with_selected_portfolio_not_raw_pool_max():
    candidates = [
        item("Very high scoring AI candidate", "OpenAI", 105, area="ai"),
        item("Strong convergence result", "Nature", 90, area="robotics", content_type="research", research_signal=True),
        item("Strong mind result", "Stanford HAI", 88, area="mind", content_type="research", research_signal=True),
        item("Another AI result", "Anthropic", 80, area="ai"),
    ]
    contract = load_editorial_contract()
    contract["ai_core_target_min"] = 1
    contract["convergence_target"] = 1
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0
    contract["min_authoritative_items"] = 0
    selected = select_regular_portfolio(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    assert {x["mission_area"] for x in selected} == {"ai_core", "convergence"}
    assert any(x["mission_selection_reason"] == "mission_target:convergence" for x in selected)


def test_weak_mission_target_does_not_displace_stronger_mainstream_candidate():
    candidates = [
        item("Strong frontier AI result", "OpenAI", 100, area="ai"),
        item("Weak consciousness commentary", "Blog", 70, area="mind"),
        item("Second strong AI result", "Anthropic", 95, area="ai"),
    ]
    contract = load_editorial_contract()
    contract["ai_core_target_min"] = 0
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 1
    contract["mind_future_target"] = 0
    contract["target_quality_floor_ratio"] = 0.88
    selected = select_regular_portfolio(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    assert [x["title"] for x in selected] == ["Strong frontier AI result", "Second strong AI result"]

def test_authority_repair_preserves_mission_area_with_same_area_replacement():
    candidates = [
        item("Strong frontier AI result", "OpenAI", 100, area="ai"),
        item("Strong convergence result", "Quantum Lab", 99, area="convergence"),
        item("Authoritative convergence result", "Nature", 90, area="convergence"),
    ]
    candidates[0]["source_tier"] = 3
    candidates[1]["source_tier"] = 3
    candidates[2]["source_tier"] = 1
    contract = load_editorial_contract()
    contract["ai_core_target_min"] = 1
    contract["convergence_target"] = 1
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0
    contract["min_authoritative_items"] = 1
    selected = select_regular_portfolio(
        candidates,
        max_posts=2,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    assert [x["mission_area"] for x in selected] == ["ai_core", "convergence"]
    assert any(x["title"] == "Authoritative convergence result" for x in selected)



def test_deepmind_robotics_does_not_match_mind_as_a_substring():
    candidate = {
        "title": "Google DeepMind humanoid robot learns from video",
        "summary": "A robotics system learns manipulation from demonstrations.",
        "category": "ai",
        "source": "Google DeepMind",
    }
    assert mission_area(candidate) == "convergence"



def test_astronomy_story_with_stale_mind_label_is_reclassified_from_content():
    candidate = {
        "title": "Francis Halzen: How an under-ice telescope is transforming astronomy",
        "summary": "A profile of neutrino astronomy and an Antarctic under-ice telescope.",
        "mission_area": "mind_cognition",
        "category": "ai",
        "content_type": "interview",
        "person_name": "Francis Halzen",
        "_ai_link": True,
        "ai_relevance": True,
    }
    assert mission_area(candidate) != "mind_cognition"
    assert candidate["mission_area"] == "unclassified"
    assert candidate["_mission_area_rejected"] == "mind_cognition_without_content_evidence"
    assert not is_mission_relevant(candidate, strict=True)


def test_actual_ai_and_mind_content_keeps_mind_cognition_classification():
    candidate = {
        "title": "AI and the mind: consciousness, self-awareness and cognitive science",
        "summary": "A discussion of machine consciousness and the philosophy of mind.",
        "mission_area": "mind_cognition",
    }
    assert mission_area(candidate) == "mind_cognition"


def test_actual_consciousness_keyword_still_maps_to_mind_cognition():
    candidate = {
        "title": "New evidence about machine consciousness and self-awareness",
        "summary": "A cognitive science analysis of artificial consciousness.",
        "category": "ai",
    }
    assert mission_area(candidate) == "mind_cognition"

def test_adaptive_policy_can_select_more_than_three_distinct_high_quality_ai_stories():
    candidates = [
        item("Google DeepMind Genie interactive world simulator launch", "Google DeepMind", 91, area="ai", content_type="news"),
        item("OpenAI coding agent capability release", "OpenAI", 89, area="ai", content_type="news"),
        item("Anthropic computer-use model update", "Anthropic", 87, area="ai", content_type="news"),
        item("NVIDIA physical AI platform announcement", "NVIDIA", 85, area="ai", content_type="news"),
        item("Meta open-source AI system release", "Meta", 83, area="ai", content_type="news"),
    ]
    contract = load_editorial_contract()
    contract.update(
        ai_core_target_min=0,
        ai_core_target_max=8,
        convergence_target=0,
        mind_cognition_target=0,
        mind_future_target=0,
        research_target=0,
        min_authoritative_items=0,
        max_same_mission_area=8,
    )
    selected = select_regular_portfolio(
        candidates,
        max_posts=8,
        max_per_source=1,
        max_per_type=8,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )
    titles = [candidate["title"] for candidate in selected]
    assert len(titles) == 5
    assert "Google DeepMind Genie interactive world simulator launch" in titles
    assert "Meta open-source AI system release" in titles


def test_major_ai_product_launch_wins_shared_portfolio_order_after_quality_floor(monkeypatch):
    routine = {
        **item("Routine AI deployment status update", "Reuters", 82.0, area="ai"),
        "summary": "A routine operational update about an AI deployment and machine learning.",
        "_test_freshness": 0.88,
    }
    product = {
        **item(
            "Google DeepMind introduces Genie 4, an interactive world simulator",
            "Google DeepMind",
            80.0,
            area="ai",
            content_type="product_news",
        ),
        "summary": "The new world model generates interactive environments in real time.",
        "description": "An AI product announcement introduces a new world simulation capability.",
        "_test_freshness": 0.73,
    }
    monkeypatch.setattr(
        selection_module,
        "freshness_score",
        lambda candidate, half_life_hours=24.0: float(candidate.get("_test_freshness", 0.0)),
    )
    contract = dict(load_editorial_contract())
    contract["ai_core_target_min"] = 0
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0

    selected = select_regular_portfolio(
        [routine, product],
        max_posts=1,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )

    assert len(selected) == 1
    assert selected[0]["title"] == product["title"]
    # Priority affects only choice order; the canonical editorial score is untouched.
    assert selected[0]["final_editorial_score"] == 80.0


def test_product_priority_does_not_bypass_relative_quality_floor(monkeypatch):
    routine = {
        **item("Routine AI deployment status update", "Reuters", 82.0, area="ai"),
        "summary": "A routine operational update about an AI deployment and machine learning.",
        "_test_freshness": 0.88,
    }
    weak_product = {
        **item(
            "Google DeepMind introduces Genie 4, an interactive world simulator",
            "Google DeepMind",
            64.0,
            area="ai",
            content_type="product_news",
        ),
        "summary": "The new world model generates interactive environments in real time.",
        "description": "An AI product announcement introduces a new world simulation capability.",
        "_test_freshness": 0.73,
    }
    monkeypatch.setattr(
        selection_module,
        "freshness_score",
        lambda candidate, half_life_hours=24.0: float(candidate.get("_test_freshness", 0.0)),
    )
    contract = dict(load_editorial_contract())
    contract["ai_core_target_min"] = 0
    contract["convergence_target"] = 0
    contract["mind_cognition_target"] = 0
    contract["mind_future_target"] = 0
    contract["research_target"] = 0
    contract["diversity_quality_floor_ratio"] = 0.80

    selected = select_regular_portfolio(
        [routine, weak_product],
        max_posts=1,
        max_per_source=1,
        max_per_type=3,
        recent_source_counts={},
        contract=contract,
        mission_aware=True,
        strict_relevance=True,
    )

    assert len(selected) == 1
    assert selected[0]["title"] == routine["title"]


def test_generic_partnership_does_not_receive_product_launch_priority():
    partnership = {
        "title": "Google DeepMind announces a corporate partnership",
        "summary": "The organizations will work together on a business initiative.",
        "source": "Google DeepMind",
        "source_tier": 1,
        "content_type": "news",
        "category": "ai",
        "_ai_link": True,
        "final_editorial_score": 80.0,
    }

    assert selection_module._bounded_portfolio_priority_boost(partnership) == 0.0


def test_ai_target_arbitration_prioritizes_product_release_within_quality_floor():
    routine = item("Routine AI deployment status update", "Reuters", 82.0, area="ai")
    product = item(
        "Google DeepMind introduces Genie 4, an interactive world simulator",
        "Google DeepMind",
        80.0,
        area="ai",
        content_type="product_news",
    )
    product["summary"] = "The new world model generates interactive environments in real time."
    product["description"] = "An AI product announcement introduces a new world simulation capability."
    weak_product = item(
        "Google DeepMind introduces a weak experimental AI product",
        "Google DeepMind Research",
        60.0,
        area="ai",
        content_type="product_news",
    )
    weak_product["summary"] = "An early prototype with limited capability."
    contract = dict(load_editorial_contract())
    contract["mission_target_quality_floor_ratio"] = 0.82

    selected = selection_module._best_ai_target_candidate(
        [routine, product, weak_product],
        contract,
    )

    assert selected is product
    assert product["final_editorial_score"] == 80.0
