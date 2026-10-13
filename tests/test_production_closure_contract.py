from scripts.production_closure_contract import (
    is_persisted_state_skip,
    posts_sent_counts,
    publish_evidence,
    selected_candidate_count,
)


def test_post_budget_zero_candidates_can_pass_with_explicit_acceptance():
    log = """
[Production Selection] total=0
[Publication Summary Budget] input=0 output=0 normal_window=0 replacement_buffer=0
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 0/0
[Production Acceptance] PASS: selected=0, published_news=0
"""
    assert selected_candidate_count(log) == 0
    assert posts_sent_counts(log) == (0, 0)
    assert publish_evidence(log) is True


def test_downstream_rejection_is_not_zero_candidate_evidence():
    log = """
[Production Selection] total=1
[Publication Summary Budget] input=1 output=1 normal_window=1
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 0/1
[Production Acceptance] PASS: fail-closed editorial rejection
"""
    assert selected_candidate_count(log) == 1
    assert publish_evidence(log) is False


def test_confirmed_delivery_requires_telegram_publication_marker():
    log = """
[Publication Summary Budget] input=1 output=1
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 education=not_due
Posts sent: 1/1
[Production Acceptance] PASS: selected=1, published_news=1
"""
    assert publish_evidence(log) is False
    assert publish_evidence(log + "\n[Telegram Published] message_id=12") is True


def test_only_skipped_state_persistence_push_is_ignored():
    run = {"event": "push", "head_commit": {"message": "chore: persist production state [skip ci]"}}
    assert is_persisted_state_skip(run, {"conclusion": "skipped"}) is True
    assert is_persisted_state_skip(run, {"conclusion": "success"}) is False
    assert is_persisted_state_skip({**run, "event": "schedule"}, {"conclusion": "skipped"}) is False
    assert is_persisted_state_skip({"event": "push", "head_commit": {"message": "other"}}, {"conclusion": "skipped"}) is False
