"""Conservative identity check for protected leader-watch stories.

Leader-watch content must not be starved merely because the same person appears
in another story. This helper therefore detects only strong title-level rewrites
of the same story and intentionally ignores broad topical similarity.
"""
from __future__ import annotations

import difflib
import re

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with",
    "about", "how", "why", "what", "this", "that", "new", "latest", "ai",
    "artificial", "intelligence", "interview", "podcast", "talk", "conversation",
}


def _tokens(value: object) -> set[str]:
    text = str(value or "").lower()
    return {
        token for token in re.findall(r"[A-Za-z][A-Za-z0-9-]*", text)
        if len(token) > 2 and token not in _STOPWORDS
    }


def _title_similarity(left: str, right: str) -> tuple[int, float, float]:
    a, b = _tokens(left), _tokens(right)
    shared = len(a & b)
    containment = shared / max(1, min(len(a), len(b)))
    sequence = difflib.SequenceMatcher(None, str(left).lower(), str(right).lower()).ratio()
    return shared, containment, sequence


def probable_same_story(candidate: dict, stored: dict) -> bool:
    """Return True only for a strong protected-story rewrite signal."""
    candidate_title = str(candidate.get("title") or candidate.get("title_text") or "")
    stored_title = str(stored.get("title") or stored.get("title_text") or "")
    if not candidate_title or not stored_title:
        return False

    candidate_leader = str(candidate.get("leader") or candidate.get("watch_person") or "").strip().lower()
    stored_leader = str(stored.get("leader") or stored.get("watch_person") or "").strip().lower()
    if not candidate_leader or not stored_leader or candidate_leader != stored_leader:
        return False

    shared, containment, sequence = _title_similarity(candidate_title, stored_title)
    if shared >= 4 and containment >= 0.55:
        return True
    if shared >= 3 and containment >= 0.65:
        return True
    if shared >= 4 and sequence >= 0.62:
        return True
    return False
