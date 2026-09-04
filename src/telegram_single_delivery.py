"""Canonical Telegram publication orchestration.

The editorial story is published as exactly one canonical full-text message.
Images are intentionally not published as companion messages. This keeps the
channel feed atomic and prevents duplicate text/photo publication.
"""
from __future__ import annotations

import html
import os
import re

import requests
import send_telegram

SAFE_TEXT_LIMIT = 3900


def _visible_length(text: str) -> int:
    """Measure Telegram-visible text, excluding HTML tags and escaped markup."""
    raw = str(text or "")
    raw = re.sub(r"<[^>]*>", "", raw)
    raw = html.unescape(raw)
    return len(raw)


def _send_html_without_raw_length_guard(text: str, source_link: str = ""):
    """Send one HTML message when raw markup exceeds the limit but visible text fits.

    Telegram applies its text limit after entity parsing. The canonical Radar
    post contains long href attributes (notably the ChatGPT navigation URL),
    so rejecting based on raw HTML length incorrectly blocks valid messages.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        raise RuntimeError("TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL تنظیم نشده است.")

    visible = _visible_length(text)
    if visible > SAFE_TEXT_LIMIT:
        print(f"[Telegram Delivery] rejected oversized visible story: visible_chars={visible} limit={SAFE_TEXT_LIMIT}", flush=True)
        return False
    if not send_telegram._telegram_preflight(token, channel):
        return False

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": channel,
            "text": str(text or ""),
            "parse_mode": "HTML",
            "disable_web_page_preview": not bool(str(source_link or "").strip()),
        },
        timeout=20,
    )
    if response.status_code != 200:
        print(f"[ERROR] Telegram HTML transport failed: {response.status_code} - {response.text}", flush=True)
        return False
    payload = response.json()
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict) or result.get("message_id") is None:
        print(f"[ERROR] Telegram HTML transport returned invalid result: {payload}", flush=True)
        return False
    return result


def _send_text_only(text: str, source_link: str = ""):
    """Publish exactly one canonical full-text Telegram message.

    Oversized visible stories are rejected before transport. HTML markup such
    as href attributes does not count toward the Telegram-visible limit.
    """
    raw_text = str(text or "")
    visible = _visible_length(raw_text)
    if visible > SAFE_TEXT_LIMIT:
        print(f"[Telegram Delivery] rejected oversized single-message story: visible_chars={visible} limit={SAFE_TEXT_LIMIT}", flush=True)
        return False

    # Preserve the established sender path for ordinary messages. When HTML
    # markup itself makes the raw string large, use the direct HTML transport
    # above so the sender's raw-length chunker cannot split href attributes.
    if len(raw_text) > SAFE_TEXT_LIMIT:
        result = _send_html_without_raw_length_guard(raw_text, source_link=source_link)
    else:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        channel = os.environ.get("TELEGRAM_CHANNEL")
        if not token or not channel:
            raise RuntimeError("TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL تنظیم نشده است.")
        if not send_telegram._telegram_preflight(token, channel):
            return False
        result = send_telegram._send_text_full(token, channel, raw_text, preview_url=source_link, preflight=False)

    if not isinstance(result, dict) or result.get("message_id") is None:
        return False

    result = dict(result)
    result["photo_message_id"] = None
    result["delivery_complete"] = True
    print(f"[Telegram Delivery] full_text={result['message_id']} photo=disabled single_message=true", flush=True)
    return result


def send(text: str, image_url: str = "", source_link: str = ""):
    """Publish exactly one Telegram message; never publish a photo companion."""
    try:
        _ = image_url
        return _send_text_only(text, source_link=source_link)
    except Exception as exc:
        print(f"[Telegram Delivery] send attempt failed without retry to prevent duplicate publication: {exc}", flush=True)
        return False


def send_to_telegram_single(text: str, image_url: str = "", source_link: str = ""):
    return send(text, image_url=image_url, source_link=source_link)
