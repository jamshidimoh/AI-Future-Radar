"""Telegram delivery adapter that preserves message identity for audience feedback."""
from __future__ import annotations

import html
import os
import re
import requests

from send_telegram import _compact_photo_caption

# Telegram sendMessage hard limit is 4096 UTF-8 characters. Keep a safety margin
# so bidi controls and HTML markup cannot push an educational post over the edge.
TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_SAFE_LIMIT = 3900


def _plain(text: str, limit: int) -> str:
    text = re.sub(r'<a\s+href=["\'][^"\']+["\']>(.*?)</a>', r'\1', str(text or ""), flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def _metadata(response):
    if response.status_code != 200:
        print(f'[ERROR] Telegram delivery failed: {response.status_code} - {response.text}', flush=True)
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    if not payload.get('ok'):
        print(f'[ERROR] Telegram delivery rejected: {payload}', flush=True)
        return False
    message = payload.get('result') or {}
    return {
        'ok': True,
        'chat_id': (message.get('chat') or {}).get('id'),
        'message_id': message.get('message_id'),
        'date': message.get('date'),
    }


def send(text: str, image_url: str = ''):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    channel = os.environ.get('TELEGRAM_CHANNEL')
    if not token or not channel:
        raise RuntimeError('TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL is not configured')

    # Never intentionally split an educational post into multiple Telegram
    # messages. The renderer is expected to stay below the safe budget.
    # If an upstream change violates the budget, fail loudly rather than
    # silently publishing a two-part lesson.
    if not image_url and len(str(text)) > TELEGRAM_SAFE_LIMIT:
        raise ValueError(
            f'Educational Telegram message exceeds safe limit: {len(str(text))} > {TELEGRAM_SAFE_LIMIT}'
        )

    base = f'https://api.telegram.org/bot{token}'
    if image_url:
        response = requests.post(
            f'{base}/sendPhoto',
            data={
                'chat_id': channel,
                'photo': image_url,
                'caption': _compact_photo_caption(text),
                'parse_mode': 'HTML',
            },
            timeout=20,
        )
    else:
        response = requests.post(
            f'{base}/sendMessage',
            data={
                'chat_id': channel,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': False,
            },
            timeout=20,
        )
    result = _metadata(response)
    if result:
        return result

    if image_url:
        response = requests.post(
            f'{base}/sendPhoto',
            data={'chat_id': channel, 'photo': image_url, 'caption': _plain(text, 1024)},
            timeout=20,
        )
    else:
        # Do not truncate educational content into a second/partial message.
        # A Telegram API failure should remain a delivery failure.
        response = requests.post(
            f'{base}/sendMessage',
            data={'chat_id': channel, 'text': _plain(text, TELEGRAM_TEXT_LIMIT), 'disable_web_page_preview': False},
            timeout=20,
        )
    return _metadata(response)
