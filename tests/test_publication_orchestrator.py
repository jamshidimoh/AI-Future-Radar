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


def test_final_story_guard_blocks_duplicate_within_current_run(monkeypatch):
    import src.publication_orchestrator as orchestrator
    import src.publication_guard as publication_guard

    monkeypatch.setattr(publication_guard, "_load_records", lambda: [])
    orchestrator._CURRENT_RUN_PUBLICATIONS.clear()
    calls = []
    rendered = "<b>📡 Same story</b>\n<blockquote>📌 <b>خلاصه</b>\nSame event summary.</blockquote>"

    first = {"title": "Same story", "summary": "Same event summary.", "link": "https://one.example/story", "_rendered_text": rendered}
    second = {"title": "Same story", "summary": "Same event summary.", "link": "https://two.example/story", "_rendered_text": rendered}

    try:
        first_outcome = publish_story(
            first,
            policy=lambda story: delivered({"message_id": None}),
            deliver=lambda story: calls.append("deliver") or delivered({"message_id": 1}),
            ledger=lambda story, result: calls.append("ledger"),
        )
        second_outcome = publish_story(
            second,
            policy=lambda story: delivered({"message_id": None}),
            deliver=lambda story: calls.append("deliver") or delivered({"message_id": 2}),
            ledger=lambda story, result: calls.append("ledger"),
        )
    finally:
        orchestrator._CURRENT_RUN_PUBLICATIONS.clear()

    assert first_outcome.status is DeliveryStatus.DELIVERED
    assert second_outcome.status is DeliveryStatus.DUPLICATE
    assert calls == ["deliver", "ledger"]
