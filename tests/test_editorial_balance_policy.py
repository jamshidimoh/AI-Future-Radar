from pathlib import Path

import yaml

from src.protected_editorial_lane import is_mind_ideas_voices_candidate
from src.unified_editorial_selection import (
    _Portfolio,
    candidate_score,
    load_editorial_contract,
    mission_area,
    select_regular_portfolio,
)


def _item(title, source, score, category, *, content_type="news", **extra):
    return {
        "title": title,
        "summary": title,
        "source": source,
        "source_tier": 1,
        "final_editorial_score": score,
        "category": category,
        "content_type": content_type,
        "research_signal": content_type in {"research", "paper", "study"},
        "_ai_link": True,
        "ai_relevance": True,
        **extra,
    }


def test_three_item_portfolio_is_ai_first_with_a_mind_or_future_slot():
    candidates = [
        _item("Frontier AI model release", "OpenAI", 96, "ai"),
        _item(
            "Sam Altman interview about AI agents and model capabilities",
            "AI Podcast",
            82,
            "ai",
            content_type="interview",
            interview_signal=True,
            leader="Sam Altman",
            watch_person="Sam Altman",
            is_leader_watch=True,
        ),
        _item("New AI reasoning capability from Anthropic", "Anthropic", 95, "ai"),
        _item("AI, consciousness and what current models tell us about cognition", "Quanta Magazine", 78, "mind"),
        _item("AI genomic analysis of gene expression", "Nature Biotechnology", 110, "bio", content_type="research"),
        _item("AI's long-term impact on work and society", "MIT Technology Review", 77, "future"),
    ]
    contract = load_editorial_contract()
    selected = select_regular_portfolio(
        candidates, max_posts=3, max_per_source=1, max_per_type=2,
        recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True,
    )
    areas = [mission_area(item) for item in selected]
    assert len(selected) == 3
    assert areas.count("ai_core") == 2
    assert "mind_cognition" in areas
    assert "future_governance" not in areas
    assert "convergence" not in areas
    assert any(item.get("leader") == "Sam Altman" for item in selected)


def test_named_leader_voice_is_preferred_when_within_quality_floor():
    contract = load_editorial_contract()
    candidates = [
        _item("Frontier AI reasoning system", "OpenAI", 100, "ai"),
        _item(
            "Yann LeCun podcast on AI world models", "Research Podcast", 83, "ai",
            content_type="podcast", interview_signal=True, leader="Yann LeCun",
        ),
        _item("Second AI model capability", "Anthropic", 98, "ai"),
    ]
    selected = select_regular_portfolio(
        candidates, max_posts=2, max_per_source=1, max_per_type=2,
        recent_source_counts={}, contract=contract, mission_aware=True, strict_relevance=True,
    )
    assert any(item.get("leader") == "Yann LeCun" for item in selected)


def test_at_most_one_genetics_led_item_is_admissible_per_portfolio():
    contract = load_editorial_contract()
    assert contract["max_genetics_per_run"] == 1
    portfolio = _Portfolio(
        contract=contract, limit=3, source_cap=2, type_cap=2,
        recent={}, mission_aware=True,
    )
    first = _item("AI genomics model studies gene expression", "Nature Biotechnology", 90, "bio", content_type="research")
    second = _item("Genetic analysis with AI predicts genome variation", "Genome Journal", 89, "genetics", content_type="research")
    portfolio.add(first, "test")
    assert not portfolio.admissible(second, repeat_source=False)


def test_at_most_one_medical_led_item_is_admissible_per_portfolio():
    contract = load_editorial_contract()
    assert contract["max_health_medical_per_run"] == 1
    portfolio = _Portfolio(
        contract=contract, limit=3, source_cap=2, type_cap=2,
        recent={}, mission_aware=True,
    )
    first = _item(
        "Machine learning diagnosis for endometriosis",
        "Nature Medicine", 91, "ai", content_type="research",
    )
    second = _item(
        "Blood transcriptomics in essential tremor correlates with clinical imaging",
        "Clinical Journal", 90, "ai", content_type="research",
    )
    portfolio.add(first, "test")
    assert not portfolio.admissible(second, repeat_source=False)


def test_medical_led_research_receives_a_diversity_penalty_against_broad_ai():
    medical = _item(
        "Machine learning diagnosis for endometriosis",
        "Nature Medicine", 90, "ai", content_type="research",
    )
    broad_ai = _item(
        "A new AI reasoning system improves tool use",
        "MIT Technology Review", 90, "ai",
    )
    assert candidate_score(medical) < candidate_score(broad_ai)
    assert load_editorial_contract()["health_medical_diversity_penalty"] == 12


def test_general_genetics_research_does_not_enter_mind_ideas_voices_lane():
    item = _item(
        "AI model predicts gene expression from genomic features",
        "Nature Biotechnology", 90, "bio", content_type="research",
    )
    assert not is_mind_ideas_voices_candidate(item)


def test_specialist_research_receives_a_real_selection_penalty():
    broad = _item("What a new AI model means for drug discovery", "MIT Technology Review", 90, "ai", content_type="research")
    specialist = _item(
        "Physics-guided deep learning inference of intramural slow-conduction depth from simulated epicardial optical mapping",
        "Specialist Journal", 90, "ai", content_type="research",
    )
    assert candidate_score(broad) > candidate_score(specialist)
    assert candidate_score(specialist) <= 80


def test_ai_future_is_preferred_over_general_convergence_when_mind_candidates_are_absent():
    candidates = [
        _item("Frontier AI model release", "OpenAI", 96, "ai"),
        _item("AI reasoning capability from Anthropic", "Anthropic", 95, "ai"),
        _item("AI future of work and next decade's labor market", "MIT Technology Review", 80, "future"),
        _item("Robotics breakthrough in autonomous systems", "MIT CSAIL", 92, "robotics", content_type="research"),
    ]
    contract = load_editorial_contract()
    # Isolate the secondary-lane arbitration: the second AI slot is disabled in this test.
    contract["ai_core_target_max"] = 1
    selected = select_regular_portfolio(
        candidates, max_posts=2, max_per_source=1, max_per_type=2,
        recent_source_counts={}, contract=contract,
        mission_aware=True, strict_relevance=True,
    )
    areas = [mission_area(item) for item in selected]
    assert areas.count("ai_core") == 1
    assert "future_governance" in areas
    assert "convergence" not in areas


def test_genetics_diversity_penalty_is_bounded_and_applied_to_genetic_stories():
    genetic = _item("AI genomics model studies gene expression", "Nature Biotechnology", 90, "bio", content_type="research")
    broad_ai = _item("New AI capability improves scientific discovery", "MIT Technology Review", 90, "ai")
    assert candidate_score(genetic) < candidate_score(broad_ai)
    assert 0 < load_editorial_contract()["genetics_diversity_penalty"] <= 30


def test_genetics_watchlist_is_not_overweighted_by_repeated_named_queries():
    watchlist = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/leader_watchlist.yaml").read_text(encoding="utf-8"))
    church_queries = [item for item in watchlist.get("google_news_queries", []) if "George Church" in str(item.get("query") or "")]
    assert len(church_queries) <= 2
    assert any("Andrej Karpathy" in str(item.get("query") or "") for item in watchlist["google_news_queries"])
