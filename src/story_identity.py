"""Canonical story identity backed by the shared hybrid event matcher."""
from __future__ import annotations

import re
from typing import Any, Iterable
from canonical_story import canonical_url
from event_identity import compare_events


def _canonical_url(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return canonical_url(item.get("canonical_url") or item.get("link") or item.get("url"))


def _event_tokens(signature: Any) -> set[str]:
    if not isinstance(signature, dict):
        return set()
    context = signature.get("context") or set()
    if isinstance(context, str):
        return {context}
    try:
        return {str(token) for token in context}
    except TypeError:
        return set()


def _material_update_tokens(signature: Any) -> set[str]:
    if not isinstance(signature, dict):
        return set()
    text = " ".join(
        str(signature.get(key) or "")
        for key in ("title_text", "title", "summary", "description")
    ).casefold()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    text = re.sub(r"\s+", " ", text).strip()
    markers: set[str] = set()
    patterns = {
        "یافته‌ها": r"(?<![\w])یافته\s+ها(?:ی)?(?![\w])",
        "شواهد": r"(?<![\w])شواهد(?![\w])",
        "مستقل": r"(?<![\w])مستقل(?![\w])",
        "دامنه": r"(?<![\w])دامنه(?![\w])",
        "مقیاس": r"(?<![\w])مقیاس(?![\w])",
        "جزئیات": r"(?<![\w])جزئیات(?![\w])",
        "علت": r"(?<![\w])علت(?![\w])",
        "کشف": r"(?<![\w])کشف(?![\w])",
        "تأیید": r"(?<![\w])(?:تأیید|تایید)(?![\w])",
        "شدت": r"(?<![\w])شدت(?![\w])",
        "خسارت": r"(?<![\w])خسارت(?![\w])",
        "رفع": r"(?<![\w])رفع(?![\w])",
    }
    for marker, pattern in patterns.items():
        if re.search(pattern, text):
            markers.add(marker)
    return markers


def _coerce_prior(prior: Any) -> dict[str, Any] | None:
    if not isinstance(prior, dict):
        return None
    if any(key in prior for key in ("title_text", "context", "anchors", "events", "personnel", "numbers")) and "title" in prior:
        title = str(prior.get("title_text") or " ".join(str(x) for x in (prior.get("title") or [])))
        context = " ".join(str(x) for x in (prior.get("context") or []))
        return {"title": title, "summary": context, "description": "", "content": "", "leader": prior.get("leader", "")}
    return prior


def _is_protected_leader(item: dict[str, Any]) -> bool:
    return bool(item.get("protected_content") and (item.get("leader") or item.get("watch_person") or item.get("_named_leader_interview") or item.get("leader_watch_protected")))


def _is_same_story(candidate: dict[str, Any], prior: Any) -> bool:
    if not isinstance(prior, dict):
        return False
    ca, cb = _canonical_url(candidate), _canonical_url(prior)
    if ca and cb and ca == cb:
        return True
    if _is_protected_leader(candidate):
        return False
    comparable = _coerce_prior(prior)
    if comparable is None:
        return False
    kind, _, _ = compare_events(candidate, comparable)
    if kind == "DUPLICATE":
        return True
    if kind == "UPDATE":
        return False
    try:
        from semantic_dedup import get_story_signature, _similarity
        candidate_sig = get_story_signature(candidate)
        prior_sig = get_story_signature(comparable) if not ("title_text" in comparable or "context" in comparable) else comparable
        return _similarity(candidate_sig, prior_sig) >= 0.45
    except Exception:
        return False


def is_story_duplicate(candidate: dict[str, Any], prior_stories: Iterable[Any]) -> bool:
    return any(_is_same_story(candidate, prior) for prior in prior_stories or [])


def deduplicate_stories(items: Iterable[dict[str, Any]], history: Iterable[Any] = ()) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    rejected_history = rejected_current = 0
    history = list(history or [])
    for item in items or []:
        if is_story_duplicate(item, history):
            rejected_history += 1
            continue
        if is_story_duplicate(item, accepted):
            rejected_current += 1
            continue
        accepted.append(dict(item))
    print(f"[Story Identity] history_duplicates={rejected_history} current_run_duplicates={rejected_current} accepted={len(accepted)}", flush=True)
    return accepted
