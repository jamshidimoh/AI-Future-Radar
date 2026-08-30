from pathlib import Path

from src.editorial_quality_policy import normal_score_allowed
from scripts.production_acceptance_guard import validate

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


def test_zero_publication_fails_when_candidates_were_selected():
    log = """
[Production Selection] canonical_period_rank=true total=2
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
"""
    ok, reason = validate(log)
    assert not ok
    assert "zero news items" in reason


def test_zero_publication_is_allowed_only_when_no_candidates_exist():
    log = """
[Production Selection] canonical_period_rank=true total=0
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
"""
    ok, reason = validate(log)
    assert ok
    assert "selected=0" in reason


def test_confirmed_education_can_satisfy_an_education_slot():
    log = """
[Production Selection] canonical_period_rank=true total=2
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=confirmed
"""
    ok, reason = validate(log)
    assert ok
    assert "education=confirmed" in reason


def test_production_state_preserves_real_baseline_fields():
    state = (ROOT / "data" / "publication_state.json").read_text(encoding="utf-8")
    assert "last_published_news_score" in state
    assert "last_published_normal_news_score" in state
