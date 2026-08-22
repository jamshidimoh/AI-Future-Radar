import telegram_single_delivery as delivery


def _configure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHANNEL", "-100123")
    monkeypatch.setattr(delivery.send_telegram, "_telegram_preflight", lambda token, channel: True)


def test_send_does_not_retry_after_ambiguous_text_failure(monkeypatch):
    calls = {"text": 0}
    _configure(monkeypatch)

    def failed_text(*args, **kwargs):
        calls["text"] += 1
        return False

    monkeypatch.setattr(delivery.send_telegram, "_send_text_full", failed_text)

    result = delivery.send("متن کامل خبر")

    assert result is False
    assert calls["text"] == 1


def test_image_is_ignored_and_canonical_text_is_published_once(monkeypatch):
    calls = {"text": [], "photo": 0}
    _configure(monkeypatch)

    long_text = "<b>📡 عنوان خبر</b>\n\n" + ("این بخش از متن خبر باید کامل باقی بماند. " * 140)

    def successful_text(token, channel, text, *, preview_url="", preflight=False):
        calls["text"].append((text, preview_url))
        return {"message_id": 101, "chat_id": -100123}

    def forbidden_photo(*args, **kwargs):
        calls["photo"] += 1
        raise AssertionError("photo delivery must never be attempted")

    monkeypatch.setattr(delivery.send_telegram, "_send_text_full", successful_text)
    monkeypatch.setattr(delivery.send_telegram, "_send_source_image", forbidden_photo)

    result = delivery.send(
        long_text,
        image_url="https://example.com/image.jpg",
        source_link="https://example.com/story",
    )

    assert result["message_id"] == 101
    assert result["photo_message_id"] is None
    assert result["delivery_complete"] is True
    assert calls["text"] == [(long_text, "https://example.com/story")]
    assert calls["photo"] == 0
    assert len(calls["text"][0][0]) > 1024


def test_no_source_link_disables_preview(monkeypatch):
    calls = []
    _configure(monkeypatch)

    def successful_text(token, channel, text, *, preview_url="", preflight=False):
        calls.append(preview_url)
        return {"message_id": 102, "chat_id": -100123}

    monkeypatch.setattr(delivery.send_telegram, "_send_text_full", successful_text)

    result = delivery.send("متن بدون منبع", source_link="")

    assert result["message_id"] == 102
    assert calls == [""]


def test_successful_text_is_complete_delivery_and_no_photo_request_occurs(monkeypatch):
    calls = {"text": 0, "photo": 0}
    _configure(monkeypatch)

    def successful_text(token, channel, text, *, preview_url="", preflight=False):
        calls["text"] += 1
        return {"message_id": 101, "chat_id": -100123}

    def forbidden_photo(*args, **kwargs):
        calls["photo"] += 1
        raise AssertionError("photo delivery must never be attempted")

    monkeypatch.setattr(delivery.send_telegram, "_send_text_full", successful_text)
    monkeypatch.setattr(delivery.send_telegram, "_send_source_image", forbidden_photo)

    result = delivery.send(
        "متن کامل خبر",
        image_url="https://example.com/image.jpg",
        source_link="https://example.com/story",
    )

    assert result["message_id"] == 101
    assert result["photo_message_id"] is None
    assert calls["text"] == 1
    assert calls["photo"] == 0
