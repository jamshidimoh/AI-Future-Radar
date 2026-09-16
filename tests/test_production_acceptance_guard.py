from scripts.production_acceptance_guard import validate

FAIL_CLOSED_EDITORIAL_REJECTION = """
[Production Selection] total=1
[Editorial Gate] skipped candidate: Create Slides, Docs, and Templates
Posts sent: 0/1
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
"""


UNEXPECTED_ZERO_PUBLICATION = """
[Production Selection] total=1
Posts sent: 0/1
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
"""


SUCCESSFUL_PUBLICATION = """
[Production Selection] total=2
[Editorial Gate] skipped candidate: candidate two
Posts sent: 1/2
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
"""


PARTIAL_PUBLICATION_WITHOUT_ACCOUNTING = """
[Production Selection] total=2
Posts sent: 1/2
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
"""


CONFIRMED_EDUCATION_RECOVERY = """
[Production Selection] total=3
Posts sent: 0/3
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
[Education Published] CONFIRMED lesson_slot=manual-validation:2026-09-01 run=345 telegram_delivery=successful
[Education Recovery] CONFIRMED slot=manual-validation:2026-09-01 run=345 publication_attempt=successful
"""


PROTECTED_TIER0_FALLBACK = """
[Production Selection] total=4
[Tier0 Interview Priority] retained=2 quota_exempt=true unique_people=true
[Canonical Story Gate] kept=3 url_rejected=0 story_rejected=0 semantic_rejected=1 protected_semantic_bypassed=1 protected_same_story_blocked=1
[Editorial Gate] skipped candidate: normal candidate one
[Editorial Gate] skipped candidate: normal candidate two
[Publication Policy] PUBLISH TIER0 interview/quote global_rank=2 tier0_rank=2 score=61.11 quality_floor=60.0 quota_exempt=true
Posts sent: 1/3
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true education=not_due
"""


PROTECTED_TIER0_WITH_POLICY_BLOCKS = """
[Production Selection] total=4
[Tier0 Interview Priority] retained=1 quota_exempt=true unique_people=true
[Canonical Story Gate] kept=4 url_rejected=0 story_rejected=0 semantic_rejected=0 protected_semantic_bypassed=0 protected_same_story_blocked=0
[Publication Policy] normal candidate one: normal_score_policy_blocked:62.11<=80.50
[Publication Policy] normal candidate two: normal_score_policy_blocked:59.68<=80.50
[Publication Policy] normal candidate three: normal_score_policy_blocked:53.20<=80.50
[Publication Policy] PUBLISH TIER0 interview/quote global_rank=4 tier0_rank=1 score=61.11 quality_floor=60.0 quota_exempt=true
Posts sent: 1/4
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true education=not_due
"""


INVALID_TIER0_FALLBACK = """
[Production Selection] total=4
[Tier0 Interview Priority] retained=0 quota_exempt=true unique_people=true
[Canonical Story Gate] kept=3 url_rejected=0 story_rejected=0 semantic_rejected=0 protected_semantic_bypassed=0 protected_same_story_blocked=0
[Editorial Gate] skipped candidate: normal candidate one
[Publication Policy] PUBLISH TIER0 interview/quote global_rank=1 tier0_rank=1 score=61.11 quality_floor=60.0 quota_exempt=true
Posts sent: 1/3
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true education=not_due
"""


UNMET_MISSION_COVERAGE = """
[Production Selection] total=6
[Mission Coverage Recovery] attempt=1 area=ai title=wrong lane status=failed
[Mission Coverage Recovery] target=1 prepared=0 attempts=3 recovered=0 status=unmet
[Production Contract] normal_news=2 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 2/6
"""


COMPACT_UNMET_MISSION_COVERAGE = """
[Production Selection] total=3
[Mission Coverage Recovery] missing_lanes=3 attempts=3 recovered=0 status=unmet
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 education=not_due
Posts sent: 1/3
"""


SATISFIED_MISSION_COVERAGE = """
[Production Selection] total=3
[Mission Coverage Recovery] missing_lanes=0 attempts=1 recovered=1 status=ok
[Production Contract] normal_news=3 normal_max=3 tier0_news=0 education=not_due
Posts sent: 3/3
"""


CURRENT_RUNTIME_CONTRACT = """
[Selection Timing] original_select candidates=9 candidate_window=6 elapsed=94.090s
[Mind/Ideas/Voices Selection] rank=1 score=50.0 normal_score=68.51 normal_rank=None title=Posts
[Dual Lane Selection] normal=7 mind_ideas_voices=2 mind_cap=2 mind_score_floor=not_applied
[Publication Summary Budget] input=8 protected=0 mind_ideas_voices=1 normal_window=6 output=5 normal_limit=6 mind_limit=2 replacement_buffer=3 normal_score_floor=55.0 mind_score_floor=not_applied
[Editorial Gate] skipped candidate: GPT-6 Astra: The next generation in intelligence for work - openai.com
[Editorial Gate] skipped candidate: Could there ever be a viable test for artificial consciousness? - aeon.co
[Publication Policy] normal candidate one: normal_score_policy_blocked:51.05<=55.0
[Publication Policy] PUBLISH normal_rank=5 score=56.33 previous_normal=57.25
[Publication Policy] PUBLISH mind_ideas_voices mind_rank=2 score=50.0 normal_floor=not_applied normal_rank=None independent_lane=true
[Production Contract] normal_news=1 normal_max=3 mind_ideas_voices=1 mind_max=2 tier0_news=0 strategic_analytical=0 strategic_max=1 mind_score_floor=not_applied normal_score_floor=55.0 education=not_due
Posts sent: 2/6
"""


CURRENT_RUNTIME_CONTRACT_WITHOUT_TIER0_EXEMPT = """
[Selection Timing] candidates=3
[Dual Lane Selection] normal=2 mind_ideas_voices=1 mind_cap=2 mind_score_floor=not_applied
[Publication Summary Budget] input=3 protected=0 mind_ideas_voices=1 normal_window=3 output=3 normal_limit=3 mind_limit=2 replacement_buffer=3 normal_score_floor=55.0 mind_score_floor=not_applied
[Publication Policy] normal candidate one: normal_score_policy_blocked:51.05<=55.0
[Publication Policy] PUBLISH normal_rank=1 score=60.0 previous_normal=57.25
[Publication Policy] PUBLISH mind_ideas_voices mind_rank=1 score=47.0 normal_floor=not_applied normal_rank=None independent_lane=true
[Production Contract] normal_news=1 normal_max=3 mind_ideas_voices=1 mind_max=2 tier0_news=0 strategic_analytical=0 strategic_max=1 mind_score_floor=not_applied normal_score_floor=55.0 education=not_due
Posts sent: 2/3
"""


def test_all_selected_candidates_rejected_downstream_is_fail_closed_pass():
    ok, message = validate(FAIL_CLOSED_EDITORIAL_REJECTION)
    assert ok is True
    assert "fail-closed editorial/policy/publication rejection/accounting verified" in message


def test_zero_publication_without_rejection_evidence_is_failure():
    ok, message = validate(UNEXPECTED_ZERO_PUBLICATION)
    assert ok is False
    assert "did not provide evidence" in message


def test_successful_publication_remains_pass_when_all_selected_are_accounted_for():
    ok, message = validate(SUCCESSFUL_PUBLICATION)
    assert ok is True
    assert "published_news=1" in message


def test_partial_publication_without_selected_set_accounting_is_failure():
    ok, message = validate(PARTIAL_PUBLICATION_WITHOUT_ACCOUNTING)
    assert ok is False
    assert "left selected candidates unaccounted" in message


def test_confirmed_education_recovery_is_accounted_for():
    ok, message = validate(CONFIRMED_EDUCATION_RECOVERY)
    assert ok is True
    assert "education=confirmed" in message


def test_protected_tier0_fallback_requires_normal_candidate_accounting():
    ok, message = validate(PROTECTED_TIER0_FALLBACK)
    assert ok is True
    assert "protected Tier-0 fallback" in message


def test_tier0_fallback_accounts_explicit_policy_blocks():
    ok, message = validate(PROTECTED_TIER0_WITH_POLICY_BLOCKS)
    assert ok is True
    assert "protected Tier-0 fallback" in message


def test_tier0_only_publication_without_complete_protection_evidence_fails():
    ok, message = validate(INVALID_TIER0_FALLBACK)
    assert ok is False
    assert "Tier-0-only publication" in message


def test_unmet_mission_coverage_is_fail_closed():
    ok, message = validate(UNMET_MISSION_COVERAGE)
    assert ok is False
    assert "mission portfolio coverage remained unmet" in message


def test_compact_unmet_mission_coverage_is_fail_closed():
    ok, message = validate(COMPACT_UNMET_MISSION_COVERAGE)
    assert ok is False
    assert "mission portfolio coverage remained unmet" in message


def test_satisfied_mission_coverage_remains_acceptable():
    ok, message = validate(SATISFIED_MISSION_COVERAGE)
    assert ok is True
    assert "published_news=3" in message


def test_current_runtime_contract_with_mind_lane_is_accepted():
    ok, message = validate(CURRENT_RUNTIME_CONTRACT)
    assert ok is True
    assert "mind_ideas_voices=1" in message


def test_current_runtime_contract_without_optional_tier0_flag_is_accepted():
    ok, message = validate(CURRENT_RUNTIME_CONTRACT_WITHOUT_TIER0_EXEMPT)
    assert ok is True
    assert "mind_ideas_voices=1" in message
