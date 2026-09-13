from src.delivery_contract import DeliveryStatus, delivered, policy_blocked
from src.production_publication_adapter import publish_production_story


def test_adapter_normalizes_transport_and_writes_ledger_only_after_delivery():
    calls = []
    outcome = publish_production_story(
        {"id": "s1"},
        policy=lambda story: delivered({"message_id": None}),
        transport=lambda story: {"message_id": 123, "chat_id": "-100"},
        ledger=lambda story, result: calls.append(result.message_id),
    )
    assert outcome.status is DeliveryStatus.DELIVERED
    assert calls == [123]


def test_adapter_policy_block_stops_transport():
    calls = []
    outcome = publish_production_story(
        {"id": "s1"},
        policy=lambda story: policy_blocked("blocked"),
        transport=lambda story: calls.append("transport") or {"message_id": 123},
        ledger=lambda story, result: calls.append("ledger"),
    )
    assert outcome.status is DeliveryStatus.POLICY_BLOCKED
    assert calls == []


def test_adapter_transport_failure_stops_ledger():
    calls = []
    outcome = publish_production_story(
        {"id": "s1"},
        policy=lambda story: delivered({"message_id": None}),
        transport=lambda story: {"ok": False, "reason": "telegram_timeout", "retryable": True},
        ledger=lambda story, result: calls.append("ledger"),
    )
    assert outcome.status is DeliveryStatus.DELIVERY_FAILED_RETRYABLE
    assert calls == []
