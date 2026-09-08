[Publication Policy] PUBLISH TIER0 interview/quote global_rank=1 tier0_rank=1 score=0.11 quota_exempt=true
Posts sent: 1/3
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true education=not_due
"""


def test_all_selected_candidates_rejected_downstream_is_fail_closed_pass():
    ok, message = validate(FAIL_CLOSED_EDITORIAL_REJECTION)
    assert ok is True
    assert "fail-closed editorial/policy/publication rejection/accounting verified" in message


def test_zero_publication_without_rejection_evidence_is_failure():
    ok, message = validate(UNEXPECTED_ZERO_PUBLICATION)
    assert ok is False
    assert "did not provide evidence" in message