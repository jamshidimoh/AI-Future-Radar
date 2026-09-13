from src.delivery_contract import (
    DeliveryStatus,
    from_legacy,
    policy_blocked,
    transport_failed,
)


def test_duplicate_is_not_transport_failure():
    outcome = from_legacy({"status": "duplicate", "reason": "semantic_story_already_published"})
    assert outcome.status is DeliveryStatus.DUPLICATE
    assert not outcome.retryable
    assert not outcome.ok


def test_policy_block_is_not_transport_failure():
    outcome = policy_blocked("normal_score_policy_blocked:96.97<=97.11")
    assert outcome.status is DeliveryStatus.POLICY_BLOCKED
    assert not outcome.retryable


def test_transport_failure_preserves_diagnostics():
    outcome = transport_failed(
        "telegram_forbidden",
        retryable=False,
        http_status=403,
        telegram_error_code=403,
        telegram_description="Forbidden: bot was blocked by the user",
    )
    assert outcome.status is DeliveryStatus.DELIVERY_FAILED_PERMANENT
    assert outcome.http_status == 403
    assert outcome.telegram_error_code == 403
    assert "blocked" in outcome.telegram_description


def test_legacy_success_requires_message_id():
    outcome = from_legacy({"ok": True, "chat_id": -1001, "message_id": 42})
    assert outcome.status is DeliveryStatus.DELIVERED
    assert outcome.ok
    assert outcome.message_id == 42
