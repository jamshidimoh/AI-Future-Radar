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
[Publication Policy] PUBLISH TIER0 interview/quote global_rank=2 tier0_rank=2 score=0.11 quota_exempt=true
Posts sent: 1/3
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true education=not_due
"""


INVALID_TIER0_FALLBACK = """
[Production Selection] total=4
[Tier0 Interview Priority] retained=0 quota_exempt=true unique_people=true
[Canonical Story Gate] kept=3 url_rejected=0 story_rejected=0 semantic_rejected=0 protected_semantic_bypassed=0 protected_same_story_blocked=0
[Editorial Gate] skipped candidate: normal candidate one
[Publication Policy] PUBLISH TIER0 interview/quote global_rank=1 tier0_rank=1 score=0.11 quota_exempt=true
Posts sent: 1/3
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true education=not_due
"""


def test_all_selected_candidates_rejected_downstream_is_fail_closed_pass():
    ok, message = validate(FAIL_CLOSED_EDITORIAL_REJECTION)
    assert ok is True
    assert "fail-closed editorial rejection" in message


def test_zero_publication_without_rejection_evidence_is_failure():
    ok, message = validate(UNEXPECTED_ZERO_PUBLICATION)
    assert ok is False
    assert "did not provide evidence" in message


def test_successful_publication_remains_pass():
    ok, message = validate(SUCCESSFUL_PUBLICATION)
    assert ok is True
    assert "published_news=1" in message


def test_confirmed_education_recovery_is_accounted_for():
    ok, message = validate(CONFIRMED_EDUCATION_RECOVERY)
    assert ok is True
    assert "education=confirmed" in message


def test_protected_tier0_fallback_requires_normal_candidate_accounting():
    ok, message = validate(PROTECTED_TIER0_FALLBACK)
    assert ok is True
    assert "protected Tier-0 fallback" in message


def test_tier0_only_publication_without_complete_protection_evidence_fails():
    ok, message = validate(INVALID_TIER0_FALLBACK)
    assert ok is False
    assert "Tier-0-only publication" in message
