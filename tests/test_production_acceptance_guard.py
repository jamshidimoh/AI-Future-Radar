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
