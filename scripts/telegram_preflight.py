"""Production-safe Telegram destination diagnostics.

This script never publishes a message. It verifies the configured bot token,
target chat, and bot posting role so a delivery failure is classified before
changing publication state.
"""
from __future__ import annotations

import os
import sys

import requests


def _call(base: str, method: str, **params):
    response = requests.get(f"{base}/{method}", params=params or None, timeout=15)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200 or not payload.get("ok"):
        raise RuntimeError(f"{method}: http={response.status_code} payload={payload}")
    return payload.get("result") or {}


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.environ.get("TELEGRAM_CHANNEL", "").strip()
    if not token or not channel:
        print("[Telegram Preflight] FAIL missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL")
        return 2

    base = f"https://api.telegram.org/bot{token}"
    try:
        bot = _call(base, "getMe")
        chat = _call(base, "getChat", chat_id=channel)
        member = _call(base, "getChatMember", chat_id=chat.get("id"), user_id=bot.get("id"))
    except Exception as exc:
        print(f"[Telegram Preflight] FAIL {exc}")
        return 1

    status = member.get("status")
    can_post = member.get("can_post_messages", "n/a")
    print(
        f"[Telegram Preflight] bot={bot.get('username') or bot.get('id')} "
        f"chat_id={chat.get('id')} type={chat.get('type')} "
        f"status={status} can_post={can_post}"
    )

    if chat.get("type") == "channel" and status not in {"administrator", "creator"}:
        print("[Telegram Preflight] FAIL bot is not an administrator/creator")
        return 1
    if chat.get("type") == "channel" and status == "administrator" and can_post is False:
        print("[Telegram Preflight] FAIL administrator cannot post messages")
        return 1

    print("[Telegram Preflight] PASS destination and posting role verified; no message sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
