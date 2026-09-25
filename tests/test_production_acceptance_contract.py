from pathlib import Path

from production_entrypoint import _bound_runtime_candidates, _is_tier0_publication_candidate
from scripts.production_acceptance_guard import validate
from src.editorial_quality_policy import NORMAL_SCORE_FLOOR, normal_score_allowed

ROOT = Path(__file__).resolve().parents[1]
MISSION_POLICY = ROOT / "config" / "mission_policy.yaml"
PRODUCTION_ENTRYPOINT = ROOT / "production_entrypoint.py"


def test_rank_one_uses_absolute_quality_floor_not_adaptive_baseline():
    assert normal_score_allowed(73.30, 73.30)
    assert normal_score_allowed(63.29, 73.30)
    assert normal_score_allowed(55.00, 73.30)
    assert not normal_score_allowed(54.99, 73.30)


def test_normal_score_rejection_diagnostic_uses_absolute_floor():
    text = PRODUCTION_ENTRYPOINT.read_text(encoding="utf-8")
    assert "normal_score_policy_blocked:{score}<floor:{NORMAL_SCORE_FLOOR}" in text
    assert "normal_score_policy_blocked:{score}<={previous_normal_score}" not in text
    assert NORMAL_SCORE_FLOOR == 55.0


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


def test_runtime_education_confirmation_overrides_earlier_not_due_summary():
    log = """
[Production Selection] canonical_period_rank=true total=13
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
[Education Published] CONFIRMED lesson_slot=manual-validation:2026-09-10 run=466 telegram_delivery=successful
"""
    ok, reason = validate(log)
    assert ok
    assert "education=confirmed" in reason


def test_runtime_education_confirmation_requires_successful_delivery():
    log = """
[Production Selection] canonical_period_rank=true total=2
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
[Education Published] CONFIRMED lesson_slot=manual-validation:2026-09-10 run=466 telegram_delivery=failed
"""
    ok, reason = validate(log)
    assert not ok
    assert "zero news items" in reason


def test_production_state_preserves_real_baseline_fields():
    state = (ROOT / "data" / "publication_state.json").read_text(encoding="utf-8")
    assert "last_published_news_score" in state
    assert "last_published_normal_news_score" in state


def test_acceptance_prefers_final_summary_budget_over_ranked_candidate_count():
    log = """
[Selection Timing] original_select candidates=15 candidate_window=6 elapsed=1.0s
[Publication Summary Budget] input=5 protected=2 normal_window=3 output=5 normal_limit=5 replacement_buffer=2 score_floor=55.0
[Production Contract] normal_news=3 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
[Publication Contract] candidate rejected reason=downstream-qa;
[Publication Contract] candidate rejected reason=downstream-policy;
Posts sent: 3/5
"""
    ok, reason = validate(log)
    assert ok, reason
    assert "selected=5" in reason




def test_mission_recovery_candidate_failure_is_ignored_when_same_lane_recovers():
    log = """
[Selection Timing] original_select candidates=8 candidate_window=6 elapsed=1.0s
[Publication Summary Budget] input=3 protected=2 normal_window=1 output=3 normal_limit=3 replacement_buffer=2 score_floor=55.0
[Mission Coverage Recovery] attempt=1 area=mind_cognition title=first candidate status=failed
[Mission Coverage Recovery] attempt=2 area=mind_cognition title=second candidate status=recovered
[Mission Coverage Recovery] area=convergence status=no_candidate
[Mission Coverage Recovery] missing_lanes=2 attempts=2 recovered=1 status=unmet
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 1/3
"""
    ok, reason = validate(log)
    assert ok, reason
    assert "hard_failures" not in reason


def test_mission_recovery_unresolved_candidate_failure_stays_fail_closed():
    log = """
[Selection Timing] original_select candidates=8 candidate_window=6 elapsed=1.0s
[Publication Summary Budget] input=3 protected=2 normal_window=1 output=3 normal_limit=3 replacement_buffer=2 score_floor=55.0
[Mission Coverage Recovery] attempt=1 area=mind_cognition title=only candidate status=failed
[Mission Coverage Recovery] missing_lanes=1 attempts=1 recovered=0 status=unmet
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 1/3
"""
    ok, reason = validate(log)
    assert not ok
    assert "hard_failures=1" in reason


def test_runtime_selection_keeps_only_publishable_protected_and_normal_candidates():
    candidates = [
        {"period_rank": 1, "normal_period_rank": None, "protected_slot": True, "final_editorial_score": 70.0},
        {"period_rank": 2, "normal_period_rank": None, "protected_slot": True, "final_editorial_score": 69.0},
        {"period_rank": 3, "normal_period_rank": None, "protected_slot": True, "final_editorial_score": 68.0},
        {"period_rank": 4, "normal_period_rank": 1, "protected_slot": False},
        {"period_rank": 5, "normal_period_rank": 2, "protected_slot": False},
        {"period_rank": 6, "normal_period_rank": 3, "protected_slot": False},
        {"period_rank": 7, "normal_period_rank": 4, "protected_slot": False},
    ]
    bounded = _bound_runtime_candidates(candidates, max_posts=3, policy={"leader_protected_max": 2, "replacement_buffer": 0})
    assert len(bounded) == 5
    assert sum(bool(x.get("protected_slot")) for x in bounded) == 2
    assert [x["normal_period_rank"] for x in bounded if not x.get("protected_slot")] == [1, 2, 3]


def test_critical_incident_with_reserved_slot_uses_tier0_publication_lane():
    assert _is_tier0_publication_candidate({"critical_ai_incident": True, "protected_slot": True})
    assert not _is_tier0_publication_candidate({"critical_ai_incident": True, "protected_slot": False})


def test_runtime_candidates_keep_publishable_lane_capacity_bounded():
    candidates = [
        {"normal_period_rank": rank, "editorial_score": 70 - rank}
        for rank in range(1, 6)
    ]
    candidates.extend(
        [
            {"protected_slot": True, "final_editorial_score": 70},
            {"protected_slot": True, "final_editorial_score": 69},
            {"protected_slot": True, "final_editorial_score": 68},
        ]
    )
    bounded = _bound_runtime_candidates(
        candidates,
        max_posts=3,
        policy={"leader_protected_max": 2, "replacement_buffer": 2},
    )
    # Replacement candidates are retained in the editorial pool and summarized lazily
    # only after a selected item fails QA/publication; initial runtime bounding remains
    # limited to publishable capacity plus protected candidates.
    assert len(bounded) == 5
    assert sum(1 for item in bounded if item.get("protected_slot")) == 2
    assert [item.get("normal_period_rank") for item in bounded if item.get("normal_period_rank") is not None] == [1, 2, 3]


def test_mission_recovery_exhausted_below_floor_is_no_candidate_not_hard_failure():
    from scripts.production_acceptance_guard import validate
    log = """[Selection Timing] candidates=5
[Publication Summary Budget] input=5 output=5
[Mission Coverage Recovery] attempt=1 area=ai_core title=A status=below_score_floor
[Mission Coverage Recovery] attempt=2 area=ai_core title=B status=below_score_floor
[Mission Coverage Recovery] attempt=3 area=ai_core title=C status=below_score_floor
[Mission Coverage Recovery] lane=ai_core status=unmet
[Mission Coverage Recovery] missing_lanes=1 attempts=3 recovered=0 status=unmet
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 education=not_due
[Production Acceptance] placeholder
"""
    ok, message = validate(log)
    assert ok
    assert "no eligible candidate" in message



def test_partial_people_bootstrap_progress_is_accepted():
    log = """
[Selection Timing] original_select candidates=10 candidate_window=6 elapsed=1.0s
[Publication Summary Budget] input=10 protected=0 normal=0 output=10 normal_limit=6 mind_limit=2 voices_limit=1 replacement_buffer=3 score_floor=55.0
[Production Contract] normal_news=0 normal_max=3 people=8 people_max=none technical_trend=0 technical_max=1 mind_ideas_voices=1 mind_max=1 voices_perspectives=1 voices_max=1 tier0_news=0 education=not_due
[People Bootstrap] status=in_progress delivered=8/30 baseline=30/30 bootstrap_at=2026-09-22T09:00:00+00:00
Posts sent: 10/10
"""
    ok, reason = validate(log)
    assert ok, reason
    assert "partial delivery is valid progress" in reason


def test_zero_people_bootstrap_progress_stays_fail_closed():
    log = """
[Selection Timing] original_select candidates=10 candidate_window=6 elapsed=1.0s
[Publication Summary Budget] input=10 protected=0 normal=0 output=10 normal_limit=6 mind_limit=2 voices_limit=1 replacement_buffer=3 score_floor=55.0
[Production Contract] normal_news=0 normal_max=3 people=0 people_max=none technical_trend=0 technical_max=1 mind_ideas_voices=0 mind_max=1 voices_perspectives=0 voices_max=1 tier0_news=0 education=not_due
[People Bootstrap] status=in_progress delivered=0/30 baseline=30/30 bootstrap_at=2026-09-22T09:00:00+00:00
Posts sent: 0/10
"""
    ok, reason = validate(log)
    assert not ok
    assert "without confirmed delivery" in reason
