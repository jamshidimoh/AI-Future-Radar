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


def _send_text_only(text: str, source_link: str = ""):
    """Publish exactly one canonical full-text Telegram message.

    ``image_url`` is deliberately absent from this internal API. Callers may
    still pass it to ``send`` for backward compatibility, but it is ignored.
    A successful text publication is the complete delivery; no second Telegram
    request is made for media.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        raise RuntimeError("TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL تنظیم نشده است.")
    if not send_telegram._telegram_preflight(token, channel):
        return False

    result = send_telegram._send_text_full(token, channel, text, preflight=False)
    if not isinstance(result, dict) or result.get("message_id") is None:
        return False

    # Keep the result schema stable for existing ledger callers while making
    # the single-message invariant explicit and observable.
    result = dict(result)
    result["photo_message_id"] = None
    result["delivery_complete"] = True
    print(
        f"[Telegram Delivery] full_text={result['message_id']} photo=disabled single_message=true",
        flush=True,
    )
    return result


def send(text: str, image_url: str = "", source_link: str = ""):
    """Publish exactly one Telegram message; never publish a photo companion."""
    try:
        # ``image_url`` is intentionally ignored. Retaining the argument avoids
        # breaking upstream callers while the publication contract is migrated.
        _ = image_url
        return _send_text_only(text, source_link=source_link)
    except Exception as exc:
        print(
            f"[Telegram Delivery] send attempt failed without retry to prevent duplicate publication: {exc}",
            flush=True,
        )
        return False


def send_to_telegram_single(text: str, image_url: str = "", source_link: str = ""):
    return send(text, image_url=image_url, source_link=source_link)
