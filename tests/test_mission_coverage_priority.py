from period_ranked_pipeline import canonical_rank_score
from src.mission_coverage_priority import annotate_recovery_candidates, historical_area_counts, mission_coverage_bonus
from src.unified_editorial_selection import mission_area


def test_mission_area_uses_keyword_classification_before_research_fallback():
    item = {"title": "Could there ever be a viable test for artificial consciousness?", "category": "research", "content_type": "research"}
    assert mission_area(item) == "mind_cognition"


def test_mission_area_does_not_default_unclassified_to_ai_core():
    item = {"title": "Observations on an unrelated historical dataset", "category": "", "content_type": "news"}
    assert mission_area(item) == "unclassified"


def test_historical_area_counts_ignore_education_and_use_recent_window():
    history = [
        {"content_type": "education", "mission_area": "mind_cognition"},
        {"content_type": "news", "mission_area": "ai_core"},
        {"content_type": "news", "mission_area": "mind_cognition"},
    ]
    assert historical_area_counts(history, 2) == {"ai_core": 1, "mind_cognition": 1}


def test_underrepresented_authoritative_mind_candidate_gets_bounded_bonus():
    contract = {"window_runs": 6, "max_posts": 3, "mind_cognition_target": 1}
    item = {"mission_area": "mind_cognition", "final_editorial_score": 54.15, "source_tier": 1}
    assert mission_coverage_bonus(item, {"ai_core": 53, "mind_cognition": 1}, contract) == 1.0
    annotated = annotate_recovery_candidates([item], [{"mission_area": "mind_cognition", "content_type": "news"}], contract)[0]
    assert annotated["mission_coverage_bonus"] == 1.0
    assert annotated["historical_mission_area_count"] == 1
    assert annotated["final_editorial_score"] == 55.15


def test_coverage_bonus_is_bounded_and_additive():
    item = {"radar_composite_score": 54.15, "signal_score": 0, "mission_coverage_bonus": 0.75}
    assert canonical_rank_score(item) == 41.36
