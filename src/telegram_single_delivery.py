"""Canonical Telegram publication orchestration.

The editorial story is published as exactly one canonical full-text message.
ChatGPT navigation uses a Radar-owned GitHub Pages resolver so Telegram never
carries an oversized ChatGPT query URL and no third-party URL shortener is needed.
"""
from __future__ import annotations

import html
import os
import re
from urllib.parse import parse_qs, quote, urlparse

import requests
import send_telegram

SAFE_TEXT_LIMIT = 3900
CHATGPT_LABEL = "بررسی بیشتر با ChatGPT"
_BIDI_MARKS = "\u2066\u2069\u2067\u200f\u200e"
_MAX_TELEGRAM_NAV_URL = 512
_RADAR_RESOLVER_URL = "https://jamshidimoh.github.io/AI-Future-Radar/chatgpt/"


def _visible_length(text: str) -> int:
    raw = str(text or "")
    raw = re.sub(r"<[^>]*>", "", raw)
    raw = html.unescape(raw)
    return len(raw)


def _extract_chatgpt_anchor(text: str):
    raw = str(text or "")
    anchor_re = re.compile(r'<a\s+href=["\']([^"\']+)["\']>\s*<b>(.*?)</b>\s*</a>', flags=re.I | re.S)
    for match in anchor_re.finditer(raw):
        label = re.sub("[" + re.escape(_BIDI_MARKS) + "]", "", html.unescape(match.group(2)))
        if label.strip() != CHATGPT_LABEL:
            continue
        url = html.unescape(match.group(1))
        replacement = f"<b>{CHATGPT_LABEL}</b>"
        return raw[:match.start()] + replacement + raw[match.end():], url
    return raw, ""


def _resolver_navigation_url(chatgpt_url: str, fallback_source: str = "") -> str:
    raw = str(chatgpt_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        if parsed.scheme != "https" or parsed.netloc.lower() not in {"chatgpt.com", "www.chatgpt.com"}:
            return ""
        prompt = parse_qs(parsed.query, keep_blank_values=True).get("q", [""])[0].strip()
        if not prompt:
            return ""
        title_match = re.search(r"(?:^|\n)عنوان:\s*(.*?)(?:\n|$)", prompt)
        source_match = re.search(r"(?:^|\n)منبع:\s*(https?://\S+)(?:\n|$)", prompt)
        if not title_match:
            print("[Telegram Delivery] ChatGPT request missing canonical title", flush=True)
            return ""
        title = title_match.group(1).strip()
        source = source_match.group(1).strip() if source_match else ""
        if not title:
            return ""
        if not source:
            source = str(fallback_source or "").strip()
        if not source:
            print("[Telegram Delivery] ChatGPT request missing canonical source", flush=True)
            return ""
        resolver = (
            _RADAR_RESOLVER_URL
            + "?t=" + quote(title, safe="")
            + "&u=" + quote(source, safe="")
        )
        if len(resolver) > _MAX_TELEGRAM_NAV_URL and fallback_source:
            source = str(fallback_source).strip()
            resolver = (
                _RADAR_RESOLVER_URL
                + "?t=" + quote(title, safe="")
                + "&u=" + quote(source, safe="")
            )
        if len(resolver) > _MAX_TELEGRAM_NAV_URL:
            print(f"[Telegram Delivery] Radar resolver URL exceeds bound: {len(resolver)}", flush=True)
            return ""
        return resolver
    except Exception as exc:
        print(f"[Telegram Delivery] Radar resolver construction failed: {exc}", flush=True)
        return ""


def _send_html_without_raw_length_guard(text: str, source_link: str = ""):
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
        navigation_url = _resolver_navigation_url(chatgpt_url, fallback_source=source_link)
        if not navigation_url:
            print("[Telegram Delivery] Radar ChatGPT resolver unavailable; refusing publication rather than emitting a broken CTA", flush=True)
            return False
        cleaned_text = cleaned_text.replace(f"<b>{CHATGPT_LABEL}</b>", f'<b><a href="{html.escape(navigation_url, quote=True)}">{CHATGPT_LABEL}</a></b>', 1)
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": channel, "text": cleaned_text, "parse_mode": "HTML", "disable_web_page_preview": not bool(str(source_link or "").strip())}, timeout=20)
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
    try:
        _ = image_url
        return _send_text_only(text, source_link=source_link)
    except Exception as exc:
        print(f"[Telegram Delivery] send attempt failed without retry to prevent duplicate publication: {exc}", flush=True)
        return False


def send_to_telegram_single(text: str, image_url: str = "", source_link: str = ""):
    return send(text, image_url=image_url, source_link=source_link)
