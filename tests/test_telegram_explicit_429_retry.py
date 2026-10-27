import json

import src.send_telegram as telegram


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


def _rate_limited(seconds):
    return FakeResponse(
        429,
        {
            "ok": False,
            "error_code": 429,
            "description": f"Too Many Requests: retry after {seconds}",
            "parameters": {"retry_after": seconds},
        },
    )


def _success(message_id=123):
    return FakeResponse(
        200,
        {"ok": True, "result": {"chat": {"id": -100123}, "message_id": message_id, "date": 1}},
    )


def test_explicit_telegram_429_retries_after_server_delay(monkeypatch):
    responses = [_rate_limited(2), _success()]
    calls = []
    sleeps = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(telegram.requests, "post", post)
    monkeypatch.setattr(telegram.time, "sleep", sleeps.append)

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result["message_id"] == 123
    assert len(calls) == 2
    assert sleeps == [3]


def test_telegram_429_retries_are_bounded(monkeypatch):
    responses = [_rate_limited(1), _rate_limited(2), _success(456)]
    calls = []
    sleeps = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(telegram.requests, "post", post)
    monkeypatch.setattr(telegram.time, "sleep", sleeps.append)

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result["message_id"] == 456
    assert len(calls) == 3
    assert sleeps == [2, 5]


def test_repeated_explicit_429_with_retry_after_margin_can_recover(monkeypatch):
    # Repeated 429s should add a bounded backoff margin beyond Telegram's delay.
    # The first retry uses only the safety margin; later retries add 8 seconds each.
    responses = [_rate_limited(8), _rate_limited(8), _rate_limited(8), _success(789)]
    calls = []
    sleeps = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(telegram.requests, "post", post)
    monkeypatch.setattr(telegram.time, "sleep", sleeps.append)

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result["message_id"] == 789
    assert len(calls) == 4
    assert sleeps == [9, 17, 25]


def test_repeated_429_retry_after_eight_seconds_recovers_with_extended_bounded_budget(monkeypatch):
    # Telegram may continue to return the same explicit wait while other bot
    # messages consume the shared rate-limit window. Honor the server delay
    # for a few more bounded attempts before failing closed.
    # This specifically covers success after more rejected attempts than the
    # previous production budget allowed.
    responses = [_rate_limited(8) for _ in range(7)] + [_success(890)]
    calls = []
    sleeps = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(telegram.requests, "post", post)
    monkeypatch.setattr(telegram.time, "sleep", sleeps.append)

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result["message_id"] == 890
    assert len(calls) == 8
    assert sleeps == [9, 17, 25, 33, 41, 49, 57]


def test_explicit_429_retry_budget_remains_bounded(monkeypatch):
    calls = []
    sleeps = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _rate_limited(1)

    monkeypatch.setattr(telegram.requests, "post", post)
    monkeypatch.setattr(telegram.time, "sleep", sleeps.append)

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result is False
    assert len(calls) == telegram.MAX_TELEGRAM_RATE_LIMIT_RETRIES + 1
    assert sleeps == [
        2 + min(index * telegram.TELEGRAM_REPEATED_429_BACKOFF_INCREMENT_SECONDS,
                telegram.TELEGRAM_REPEATED_429_BACKOFF_MAX_SECONDS)
        for index in range(telegram.MAX_TELEGRAM_RATE_LIMIT_RETRIES)
    ]


def test_ambiguous_server_error_is_not_retried(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(500, {"ok": False, "error_code": 500, "description": "Internal Server Error"})

    monkeypatch.setattr(telegram.requests, "post", post)
    monkeypatch.setattr(telegram.time, "sleep", lambda _: (_ for _ in ()).throw(AssertionError("must not sleep/retry")))

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result is False
    assert len(calls) == 1


def test_unbounded_retry_after_is_not_retried(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _rate_limited(999)

    monkeypatch.setattr(telegram.requests, "post", post)

    result = telegram._send_text_full("token", "-100123", "خبر معتبر", preflight=False)

    assert result is False
    assert len(calls) == 1
