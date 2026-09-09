"""Canonical story identity backed by the shared hybrid event matcher."""
from __future__ import annotations

from typing import Any, Iterable
from canonical_story import canonical_url
from event_identity import compare_events


def _canonical_url(item: Any) -> str:
    if not isinstance(item, dict): return ""
    return canonical_url(item.get("canonical_url") or item.get("link") or item.get("url"))


def _is_same_story(candidate: dict[str, Any], prior: Any) -> bool:
    if not isinstance(prior, dict):
        return False
    ca, cb = _canonical_url(candidate), _canonical_url(prior)
    if ca and cb and ca == cb:
        return True
    kind, _, _ = compare_events(candidate, prior)
    return kind == "DUPLICATE"


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
