"""Canonical Telegram publication orchestration.

The editorial story is published as exactly one canonical full-text message.
Images are intentionally not published as companion messages. This keeps the
channel feed atomic and prevents duplicate text/photo publication.
"""
from __future__ import annotations

import html
import os
import re
from urllib.parse import urlencode

import requests
import send_telegram

SAFE_TEXT_LIMIT = 3900
CHATGPT_LABEL = "بررسی بیشتر با ChatGPT"
_BIDI_MARKS = "\u2066\u2069\u2067\u200f\u200e"
_SHORTENER_URL = "https://is.gd/create.php"
_MAX_TELEGRAM_NAV_URL = 512


def _visible_length(text: str) -> int:
    """Measure Telegram-visible text, excluding HTML tags and escaped markup."""
    raw = str(text or "")
    raw = re.sub(r"<[^>]*>", "", raw)
    raw = html.unescape(raw)
    return len(raw)


def _extract_chatgpt_anchor(text: str):
    """Extract the ChatGPT URL from its HTML anchor and replace the anchor."""
    raw = str(text or "")
    anchor_re = re.compile(
        r'<a\s+href=["\']([^"\']+)["\']>\s*<b>(.*?)</b>\s*</a>',
        flags=re.I | re.S,
    )
    for match in anchor_re.finditer(raw):
        label = re.sub("[" + re.escape(_BIDI_MARKS) + "]", "", html.unescape(match.group(2)))
        if label.strip() != CHATGPT_LABEL:
            continue
        url = html.unescape(match.group(1))
        replacement = f"<b>{CHATGPT_LABEL}</b>"
        cleaned = raw[:match.start()] + replacement + raw[match.end():]
        return cleaned, url
    return raw, ""


def _shorten_navigation_url(url: str) -> str:
    """Return a bounded navigation URL; fail closed if shortening is unavailable."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    if len(raw) <= _MAX_TELEGRAM_NAV_URL:
        return raw
    try:
        response = requests.post(
            _SHORTENER_URL,
            data={"format": "simple", "url": raw},
            timeout=20,
        )
        if response.status_code != 200:
            print(f"[Telegram Delivery] navigation shortener failed: {response.status_code}", flush=True)
            return ""
        short = response.text.strip()
        if not re.fullmatch(r"https://is\.gd/[A-Za-z0-9_-]+", short):
            print("[Telegram Delivery] navigation shortener returned invalid URL", flush=True)
            return ""
        return short
    except requests.RequestException as exc:
        print(f"[Telegram Delivery] navigation shortener unavailable: {exc}", flush=True)
        return ""


def _send_html_without_raw_length_guard(text: str, source_link: str = ""):
    """Send one HTML message when raw markup exceeds the limit but visible text fits."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        raise RuntimeError("TELEGRAM_BOT_TOKEN یا TELEGRAM_CHANNEL تنظیم نشده است.")

    cleaned_text, chatgpt_url = _extract_chatgpt_anchor(text)
    visible = _visible_length(cleaned_text)
    if visible > SAFE_TEXT_LIMIT:
        print(f"[Telegram Delivery] rejected oversized visible story: visible_chars={visible} limit={SAFE_TEXT_LIMIT}", flush=True)
        return False
    if not send_telegram._telegram_preflight(token, channel):
        return False

    if chatgpt_url:
        navigation_url = _shorten_navigation_url(chatgpt_url)
        if not navigation_url:
            print("[Telegram Delivery] ChatGPT navigation unavailable; refusing publication rather than emitting a broken CTA", flush=True)
            return False
        escaped_nav = html.escape(navigation_url, quote=True)
        cleaned_text = cleaned_text.replace(
            f"<b>{CHATGPT_LABEL}</b>",
            f'<b><a href="{escaped_nav}">{CHATGPT_LABEL}</a></b>',
            1,
        )
        if len(navigation_url) > _MAX_TELEGRAM_NAV_URL:
            print("[Telegram Delivery] bounded navigation URL invariant violated", flush=True)
            return False

    data = {
        "chat_id": channel,
        "text": cleaned_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": not bool(str(source_link or "").strip()),
    }

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
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
    """Publish exactly one canonical full-text Telegram message."""
    raw_text = str(text or "")
    visible = _visible_length(raw_text)
    if visible > SAFE_TEXT_LIMIT:
        print(f"[Telegram Delivery] rejected oversized single-message story: visible_chars={visible} limit={SAFE_TEXT_LIMIT}", flush=True)
        return False

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
