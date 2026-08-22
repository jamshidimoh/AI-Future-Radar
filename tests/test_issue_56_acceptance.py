from src.delivery_contract import DeliveryStatus, delivered, duplicate, policy_blocked, transport_failed
from src.publication_orchestrator import publish_story


def test_duplicate_never_reaches_delivery_or_ledger():
    calls = []
    outcome = publish_story(
        {"id": "s1"},
        policy=lambda story: duplicate("already_seen"),
        deliver=lambda story: calls.append("delivery") or delivered({"message_id": 10}),
        ledger=lambda story, result: calls.append("ledger"),
    )
    assert outcome.status is DeliveryStatus.DUPLICATE
    assert calls == []


def test_policy_block_never_reaches_delivery_or_ledger():
    calls = []
    outcome = publish_story(
        {"id": "s1"},
        policy=lambda story: policy_blocked("quota"),
        deliver=lambda story: calls.append("delivery") or delivered({"message_id": 10}),
        ledger=lambda story, result: calls.append("ledger"),
    )
    assert outcome.status is DeliveryStatus.POLICY_BLOCKED
    assert calls == []


def test_retryable_transport_failure_never_reaches_ledger():
    calls = []
    outcome = publish_story(
        {"id": "s1"},
        policy=lambda story: delivered({"message_id": None}),
        deliver=lambda story: calls.append("delivery") or transport_failed("timeout", retryable=True),
        ledger=lambda story, result: calls.append("ledger"),
    )
    assert outcome.status is DeliveryStatus.DELIVERY_FAILED_RETRYABLE
    assert outcome.retryable is True
    assert calls == ["delivery"]


def test_ledger_requires_confirmed_telegram_message_id():
    calls = []
    outcome = publish_story(
        {"id": "s1"},
        policy=lambda story: delivered({"message_id": None}),
        deliver=lambda story: delivered({"message_id": 987, "chat_id": "-100"}),
        ledger=lambda story, result: calls.append(result.message_id),
    )
    assert outcome.ok is True
    assert calls == [987]
