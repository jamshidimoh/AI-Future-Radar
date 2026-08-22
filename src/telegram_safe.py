"""Reliable Telegram delivery with a plain-text fallback for malformed HTML entities."""
from __future__ import annotations

import html
import os
import re
import requests

from send_telegram import send_to_telegram as _send_html

TELEGRAM_LIMIT = 4096
PHOTO_CAPTION_LIMIT = 1024


def _plain(text: str, limit: int) -> str:
    text = str(text or "")
    text = re.sub(r"<a\s+href=[\"'][^\"']+[\"']>(.*?)</a>", r"\1", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def send_to_telegram_safe(text: str, image_url: str = "") -> bool:
    """Send formatted HTML first; if Telegram rejects entity parsing, retry plain text."""
    if _send_html(text, image_url=image_url):
        return True

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL")
    if not token or not channel:
        return False

    try:
        if image_url:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={
                    "chat_id": channel,
                    "photo": image_url,
                    "caption": _plain(text, PHOTO_CAPTION_LIMIT),
                },
                timeout=20,
            )
        else:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={
                    "chat_id": channel,
                    "text": _plain(text, TELEGRAM_LIMIT),
                    "disable_web_page_preview": False,
                },
                timeout=20,
            )
        if response.status_code == 200:
            print("  ✓ Telegram plain-text fallback sent", flush=True)
            return True
        print(f"[ERROR] Telegram fallback failed: {response.status_code} - {response.text}", flush=True)
    except requests.RequestException as exc:
        print(f"[ERROR] Telegram fallback request failed: {exc}", flush=True)
    return False
