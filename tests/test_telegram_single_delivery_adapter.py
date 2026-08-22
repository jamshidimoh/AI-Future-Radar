import src.telegram_single_delivery as adapter


def test_telegram_single_delivery_returns_one_canonical_text_message(monkeypatch):
    calls = []

    def fake_publish(text, source_link=""):
        calls.append((text, source_link))
        return {
            "ok": True,
            "message_id": 123,
            "photo_message_id": None,
            "chat_id": -1001,
            "delivery_complete": True,
        }

    monkeypatch.setattr(adapter, "_send_text_only", fake_publish)
    result = adapter.send(
        "text",
        image_url="https://example.com/a.jpg",
        source_link="https://example.com/story",
    )

    assert result["message_id"] == 123
    assert result["photo_message_id"] is None
    assert result["delivery_complete"] is True
    assert calls == [("text", "https://example.com/story")]


def test_telegram_single_delivery_does_not_retry_after_failed_publication(monkeypatch):
    calls = []

    def failed_publish(text, source_link=""):
        calls.append((text, source_link))
        return False

    monkeypatch.setattr(adapter, "_send_text_only", failed_publish)

    result = adapter.send("text")

    assert result is False
    assert len(calls) == 1
