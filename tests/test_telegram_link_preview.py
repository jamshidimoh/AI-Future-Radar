import json

import send_telegram


class _FakeResponse:
    status_code = 200
    text = '{"ok": true, "result": {"message_id": 321, "chat": {"id": -100123}}}'

    def json(self):
        return {"ok": True, "result": {"message_id": 321, "chat": {"id": -100123}}}


class _DynamicResponse:
    status_code = 200

    def __init__(self, message_id):
        self.message_id = message_id
        self.text = '{"ok": true, "result": {"message_id": %d, "chat": {"id": -100123}}}' % message_id

    def json(self):
        return {"ok": True, "result": {"message_id": self.message_id, "chat": {"id": -100123}}}


def test_send_text_full_requests_source_preview_once(monkeypatch):
    calls = []
    monkeypatch.setattr(send_telegram, "_telegram_preflight", lambda token, channel: True)

    def fake_post(url, data, timeout):
        calls.append(data)
        return _FakeResponse()

    monkeypatch.setattr(send_telegram.requests, "post", fake_post)

    result = send_telegram._send_text_full(
        "متن خبر",
        "-100123",
        "متن خبر",
        preview_url="https://example.com/story",
        preflight=False,
    )

    assert result["message_id"] == 321
    assert len(calls) == 1
    options = json.loads(calls[0]["link_preview_options"])
    assert options == {
        "is_disabled": False,
        "url": "https://example.com/story",
        "prefer_large_media": True,
        "show_above_text": True,
    }


def test_send_text_full_disables_preview_when_source_link_missing(monkeypatch):
    calls = []

    def fake_post(url, data, timeout):
        calls.append(data)
        return _FakeResponse()

    monkeypatch.setattr(send_telegram.requests, "post", fake_post)

    result = send_telegram._send_text_full(
        "متن خبر",
        "-100123",
        "متن خبر",
        preview_url="",
        preflight=False,
    )

    assert result["message_id"] == 321
    options = json.loads(calls[0]["link_preview_options"])
    assert options == {"is_disabled": True}


def test_long_text_uses_preview_only_on_first_chunk(monkeypatch):
    calls = []

    long_text = ("بخش خبر\n" * 600)

    def fake_post(url, data, timeout):
        calls.append(data)
        return _DynamicResponse(400 + len(calls))

    monkeypatch.setattr(send_telegram.requests, "post", fake_post)

    result = send_telegram._send_text_full(
        "token",
        "-100123",
        long_text,
        preview_url="https://example.com/story",
        preflight=False,
    )

    assert result["message_id"] == 400 + len(calls)
    assert len(calls) > 1
    first = json.loads(calls[0]["link_preview_options"])
    rest = [json.loads(call["link_preview_options"]) for call in calls[1:]]
    assert first["is_disabled"] is False
    assert first["url"] == "https://example.com/story"
    assert all(options == {"is_disabled": True} for options in rest)
