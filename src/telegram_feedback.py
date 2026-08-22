"""Native Telegram audience-feedback ingestion and scoring."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

REACTION_WEIGHTS = {"👍": 1.0, "❤️": 1.2, "🔥": 1.5, "🤔": -0.8, "💡": 1.3}


def _reaction_emoji(reaction: dict[str, Any]) -> str | None:
    if reaction.get("type") == "emoji":
        return reaction.get("emoji")
    return None


def _default_store() -> dict[str, Any]:
    return {"version": 2, "updated_at": 0, "last_update_id": 0, "messages": {}}


def load_feedback(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return _default_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_store()
        base = _default_store()
        base.update(data)
        base.setdefault("messages", {})
        return base
    except (OSError, json.JSONDecodeError):
        return _default_store()


def save_feedback(store: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    store["updated_at"] = int(time.time())
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _message_key(chat_id: int | str, message_id: int) -> str:
    return f"{chat_id}:{message_id}"


def _ensure_message(store: dict[str, Any], chat_id: int | str, message_id: int) -> dict[str, Any]:
    key = _message_key(chat_id, message_id)
    return store["messages"].setdefault(key, {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction_counts": {},
        "reaction_events": 0,
        "comment_count": 0,
        "comment_events": 0,
        "last_comment_at": 0,
    })


def register_post(store: dict[str, Any], delivery: dict[str, Any], item: dict[str, Any]) -> None:
    """Persist Story metadata against the exact Telegram message identity."""
    chat_id = delivery.get("chat_id")
    message_id = delivery.get("message_id")
    if chat_id is None or message_id is None:
        return
    record = _ensure_message(store, chat_id, int(message_id))
    for key in ("source", "content_type", "category", "leader", "watch_person", "title", "link"):
        if item.get(key) is not None:
            record[key] = item.get(key)
    record["posted_at"] = int(delivery.get("date") or time.time())


def _apply_reaction_change(record: dict[str, Any], new_reactions: list[dict[str, Any]]) -> None:
    record["reaction_events"] = int(record.get("reaction_events", 0)) + 1
    record["last_reaction_at"] = int(time.time())
    record["last_user_reactions"] = [e for e in (_reaction_emoji(x) for x in new_reactions) if e]


def _apply_reaction_counts(record: dict[str, Any], reactions: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for item in reactions:
        if not isinstance(item, dict):
            continue
        emoji = _reaction_emoji(item.get("type", {}))
        if emoji:
            counts[emoji] = int(item.get("total_count", 0))
    if counts:
        record["reaction_counts"] = counts


def ingest_update(store: dict[str, Any], update: dict[str, Any]) -> bool:
    changed = False

    reaction_update = update.get("message_reaction")
    if isinstance(reaction_update, dict):
        chat = reaction_update.get("chat") or {}
        chat_id = chat.get("id")
        message_id = reaction_update.get("message_id")
        if chat_id is not None and message_id is not None:
            record = _ensure_message(store, chat_id, int(message_id))
            _apply_reaction_change(record, reaction_update.get("new_reaction") or [])
            changed = True

    reaction_count_update = update.get("message_reaction_count")
    if isinstance(reaction_count_update, dict):
        chat = reaction_count_update.get("chat") or {}
        chat_id = chat.get("id")
        message_id = reaction_count_update.get("message_id")
        if chat_id is not None and message_id is not None:
            record = _ensure_message(store, chat_id, int(message_id))
            _apply_reaction_counts(record, reaction_count_update.get("reactions") or [])
            record["last_reaction_at"] = int(time.time())
            changed = True

    message = update.get("message")
    if isinstance(message, dict):
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        if chat_id is not None and message_id is not None:
            reply = message.get("reply_to_message") or {}
            root_id = reply.get("message_id") or message.get("message_thread_id")
            if root_id is not None and (message.get("text") or message.get("caption")):
                record = _ensure_message(store, chat_id, int(root_id))
                record["comment_count"] = int(record.get("comment_count", 0)) + 1
                record["comment_events"] = int(record.get("comment_events", 0)) + 1
                record["last_comment_at"] = int(time.time())
                changed = True

    if changed:
        store["last_update_id"] = max(int(store.get("last_update_id", 0)), int(update.get("update_id", 0)))
    return changed


def feedback_score(record: dict[str, Any]) -> float:
    counts = record.get("reaction_counts") or {}
    reaction_component = sum(int(counts.get(emoji, 0)) * weight for emoji, weight in REACTION_WEIGHTS.items())
    comments = int(record.get("comment_count", 0))
    engagement = (reaction_component * 0.8) + (min(comments, 50) * 0.35)
    return round(engagement, 2)


def _record_score(record: dict[str, Any]) -> float:
    score = feedback_score(record)
    record["feedback_score"] = score
    record["feedback_count"] = sum((record.get("reaction_counts") or {}).values()) + int(record.get("comment_count", 0))
    return score


def enrich_item_with_feedback(item: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    chat_id = item.get("telegram_chat_id") or item.get("telegram_channel_id")
    message_id = item.get("telegram_message_id")
    if chat_id is None or message_id is None:
        enriched["audience_feedback_score"] = 0.0
        return enriched
    record = store.get("messages", {}).get(_message_key(chat_id, int(message_id)))
    if not record:
        enriched["audience_feedback_score"] = 0.0
        return enriched
    enriched["audience_feedback_score"] = _record_score(record)
    enriched["telegram_reaction_counts"] = record.get("reaction_counts", {})
    enriched["telegram_comment_count"] = int(record.get("comment_count", 0))
    return enriched


def poll_updates(token: str, store: dict[str, Any], timeout: int = 1, limit: int = 100) -> int:
    offset = int(store.get("last_update_id", 0)) + 1
    params = {
        "offset": offset,
        "limit": limit,
        "timeout": timeout,
        "allowed_updates": json.dumps(["message_reaction", "message_reaction_count"]),
    }
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=max(timeout + 5, 10))
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(str(payload))
    changed = 0
    for update in payload.get("result") or []:
        if ingest_update(store, update):
            changed += 1
    return changed


def ingest_from_env(path: str | Path) -> int:
    token = __import__("os").environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return 0
    store = load_feedback(path)
    try:
        changed = poll_updates(token, store)
    except requests.RequestException as exc:
        print(f"[WARN] Telegram feedback polling unavailable: {exc}", flush=True)
        return 0
    except Exception as exc:
        print(f"[WARN] Telegram feedback ingestion skipped: {exc}", flush=True)
        return 0
    if changed:
        save_feedback(store, path)
    return changed
