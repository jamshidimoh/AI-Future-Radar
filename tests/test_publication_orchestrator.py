from src.delivery_contract import DeliveryStatus, delivered, policy_blocked, transport_failed
from src.publication_orchestrator import publish_story


def test_policy_block_does_not_call_transport_or_ledger():
    calls = []

    outcome = publish_story(
        {"title": "x"},
        policy=lambda story: policy_blocked("policy"),
        deliver=lambda story: calls.append("deliver") or delivered({"message_id": 1}),
        ledger=lambda story, result: calls.append("ledger"),
    )

    assert outcome.status is DeliveryStatus.POLICY_BLOCKED
    assert calls == []


def test_transport_failure_does_not_write_ledger():
    calls = []

    outcome = publish_story(
        {"title": "x"},
        policy=lambda story: delivered({"message_id": None}),
        deliver=lambda story: calls.append("deliver") or transport_failed("timeout", retryable=True),
        ledger=lambda story, result: calls.append("ledger"),
    )

    assert outcome.status is DeliveryStatus.DELIVERY_FAILED_RETRYABLE
    assert calls == ["deliver"]


def test_ledger_requires_confirmed_message_id():
    calls = []

    outcome = publish_story(
        {"title": "x"},
        policy=lambda story: delivered({"message_id": None}),
        deliver=lambda story: delivered({"message_id": 42, "chat_id": "-100"}),
        ledger=lambda story, result: calls.append(result.message_id),
    )

    assert outcome.status is DeliveryStatus.DELIVERED
    assert outcome.message_id == 42
    assert calls == [42]
