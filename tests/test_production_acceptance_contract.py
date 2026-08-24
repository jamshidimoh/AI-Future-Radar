from pathlib import Path

from src.editorial_quality_policy import normal_score_allowed

ROOT = Path(__file__).resolve().parents[1]
MISSION_POLICY = ROOT / "config" / "mission_policy.yaml"


def test_rank_one_never_bypasses_adaptive_baseline():
    assert normal_score_allowed(73.30, 73.30)
    assert not normal_score_allowed(63.29, 73.30)
    assert normal_score_allowed(63.30, 73.30)


def test_mission_portfolio_is_explicit_and_not_generic_ai_only():
    text = MISSION_POLICY.read_text(encoding="utf-8")
    for area in ("ai_core:", "convergence:", "mind_cognition:", "future_governance:"):
        assert area in text
    assert "community_max: 0" in text
    assert "min_unique_sources: 3" in text
    assert "max_same_source: 1" in text
    assert "min_authoritative_items: 2" in text


def test_acceptance_contract_allows_safe_zero_publication():
    contract = (ROOT / "docs" / "PRODUCTION_FINAL_ACCEPTANCE.md").read_text(encoding="utf-8")
    assert "publishes zero news items" in contract
    assert "normal_rank=1" in contract
    assert "confirmed delivery" in contract


def test_production_state_preserves_real_baseline_fields():
    state = (ROOT / "data" / "publication_state.json").read_text(encoding="utf-8")
    assert "last_published_news_score" in state
    assert "last_published_normal_news_score" in state
