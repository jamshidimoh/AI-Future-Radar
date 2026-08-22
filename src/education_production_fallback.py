"""Independent production publisher for the required education lesson.

Education is a scheduled product stream, not a news candidate.  This module
publishes it after the news pipeline has completed, so news selection/seen
filters cannot accidentally remove the required lesson.
"""
from __future__ import annotations

from typing import Any


def publish_required_education(*, run_number: int, feedback_path: Any, cadence: dict, rewrite_fn, fetch_builder, commit_lesson, format_post, send, load_feedback, register_post, save_feedback) -> bool:
    item = fetch_builder()
    if not item:
        print("[Education Publication] build failed", flush=True)
        return False
    item = rewrite_fn(item)
    if not item:
        print("[Education Publication] Persian rewrite failed", flush=True)
        return False

    text = format_post(item)
    outcome = send(text, image_url="", source_link=str(item.get("link") or item.get("url") or ""))
    message_id = getattr(outcome, "message_id", None)
    if message_id is None and isinstance(outcome, dict):
        message_id = outcome.get("message_id")
    if message_id is None:
        print("[Education Publication] Telegram delivery failed: no message_id", flush=True)
        return False

    chat_id = getattr(outcome, "chat_id", None)
    if chat_id is None and isinstance(outcome, dict):
        chat_id = outcome.get("chat_id")
    store = load_feedback(feedback_path)
    meta = outcome.as_dict() if hasattr(outcome, "as_dict") else {"message_id": message_id, "chat_id": chat_id}
    register_post(store, meta, {**item, "content_type": "education", "publication_identity": f"education:{int(item.get('education_id', 0) or 0)}"})
    save_feedback(store, feedback_path)
    commit_lesson(int(item.get("education_id", 0) or 0))
    cadence["last_education_run"] = run_number
    print(f"[Education Publication] confirmed lesson={item.get('education_id')} message_id={message_id}", flush=True)
    return True
