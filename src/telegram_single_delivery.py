"""Canonical Telegram publication orchestration.

The editorial story is published as exactly one canonical full-text message.
Images are intentionally not published as companion Telegram messages. This
keeps the channel feed atomic, prevents the recurring text-then-photo double
message, and removes the Telegram photo-caption path from the editorial
publication contract.
"""
from __future__ import annotations

import os

import send_telegram

SAFE_TEXT_LIMIT = 3900


def _send_text_only(text: str, source_link: str = ""):
    """Publish exactly one canonical full-text Telegram message.

    Oversized stories are rejected before any Telegram request. They are never
    split into multiple messages because one story is one publication unit.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        raise RuntimeError("TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL تنظیم نشده است.")
    if len(str(text or "")) > SAFE_TEXT_LIMIT:
        print(f"[Telegram Delivery] rejected oversized single-message story: chars={len(str(text or ''))} limit={SAFE_TEXT_LIMIT}", flush=True)
        return False
    if not send_telegram._telegram_preflight(token, channel):
        return False

    result = send_telegram._send_text_full(token, channel, text, preview_url=source_link, preflight=False)
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
