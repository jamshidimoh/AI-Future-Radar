"""Canonical story identity and duplicate policy.

This module deliberately separates *duplicate* detection from broad topical
similarity. Shared entities (for example OpenAI, AI, NVIDIA, LLM) are not
sufficient evidence that two items describe the same story.
"""
from __future__ import annotations

import difflib
import re
from typing import Any, Iterable

from semantic_dedup import get_story_signature, _decode_signature

_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are",
    "with", "new", "how", "what", "why", "this", "that", "it", "its", "by", "at",
    "as", "be", "will", "can", "has", "have", "into", "over", "after", "says",
    "said", "latest", "update", "news", "podcast", "episode", "interview", "talk",
    "در", "به", "از", "با", "را", "که", "این", "آن", "و", "یا", "برای", "تا",
    "بر", "هم", "نیز", "یک", "می", "شود", "است", "های", "ها", "کرد", "شد",
}


def _normalize(text: Any) -> str:
    text = str(text or "").lower().replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-zA-Z\u0600-\u06FF0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: Any) -> set[str]:
    return {
        token for token in re.findall(r"[a-zA-Z\u0600-\u06FF0-9_]+", _normalize(text))
        if token not in _STOPWORDS and len(token) > 2
    }


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a and b else 0.0


def _canonical_url(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("canonical_url") or item.get("link") or item.get("url") or "").strip().rstrip("/")


def _signature_parts(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if "title_text" in value or "context" in value or "anchors" in value:
            decoded = _decode_signature(value) or value
        else:
            return get_story_signature(value)
    else:
        decoded = _decode_signature(value)
    if isinstance(decoded, dict) and ("title" in decoded or "title_text" in decoded):
        return decoded
    return get_story_signature(str(value or ""))


def _title_text(sig: dict[str, Any]) -> str:
    return _normalize(sig.get("title_text") or " ".join(sig.get("title", [])))


def _context(sig: dict[str, Any]) -> set[str]:
    return set(sig.get("context") or sig.get("title") or [])


def _is_protected_leader_interview(item: Any) -> bool:
    """Identify the narrow protected-interview contract without importing main."""
    if not isinstance(item, dict):
        return False
    if not item.get("protected_content"):
        return False
    if str(item.get("protected_reason") or "").strip() != "leader_interview_or_activity":
        return False
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if not leader:
        return False
    explicit = item.get("interview_signal") or item.get("interview_format") or item.get("is_interview")
    if explicit is True:
        return True
    text = _normalize(" ".join(str(item.get(k) or "") for k in ("title", "summary", "description")))
    return any(term in text for term in (
        "interview", "conversation", "fireside", "q&a", "question and answer",
        "talk with", "talks with", "speaks with", "in conversation", "sits down with",
        "مصاحبه", "گفتگو", "گفت و گو", "پرسش و پاسخ",
    ))


def _is_same_story(candidate: dict[str, Any], prior: Any) -> bool:
    """Return True only when evidence supports story identity."""
    candidate_sig = get_story_signature(candidate)
    prior_sig = _signature_parts(prior)

    candidate_url = _canonical_url(candidate)
    prior_url = _canonical_url(prior) if isinstance(prior, dict) else ""
    if candidate_url and prior_url and candidate_url == prior_url:
        return True

    title_a = _title_text(candidate_sig)
    title_b = _title_text(prior_sig)
    if not title_a or not title_b:
        return False

    title_tokens_a = set(candidate_sig.get("title") or _tokens(title_a))
    title_tokens_b = set(prior_sig.get("title") or _tokens(title_b))
    title_j = _jaccard(title_tokens_a, title_tokens_b)
    title_sequence = difflib.SequenceMatcher(None, title_a, title_b).ratio()

    # Protected leader interviews have a deliberately narrower history policy:
    # exact URL/title identity remains a duplicate, but broad semantic/context
    # similarity must not erase a distinct interview about the same leader.
    # This is intentionally limited to the protected interview contract.
    if _is_protected_leader_interview(candidate):
        if title_sequence >= 0.96 or title_j >= 0.92:
            return True
        return False

    context_j = _jaccard(_context(candidate_sig), _context(prior_sig))
    leader_a = _normalize(candidate_sig.get("leader"))
    leader_b = _normalize(prior_sig.get("leader"))
    events_a = set(candidate_sig.get("events") or [])
    events_b = set(prior_sig.get("events") or [])
    numbers_a = set(candidate_sig.get("numbers") or [])
    numbers_b = set(prior_sig.get("numbers") or [])

    if numbers_a and numbers_b and numbers_a != numbers_b:
        return False
    if title_sequence >= 0.86 or title_j >= 0.80:
        return True
    if title_j >= 0.55 and context_j >= 0.55:
        return True
    if leader_a and leader_a == leader_b and events_a & events_b and context_j >= 0.55:
        return True
    if events_a & events_b and context_j >= 0.72 and title_j >= 0.45:
        return True
    return False


def is_story_duplicate(candidate: dict[str, Any], prior_stories: Iterable[Any]) -> bool:
    return any(_is_same_story(candidate, prior) for prior in prior_stories or [])


def deduplicate_stories(items: Iterable[dict[str, Any]], history: Iterable[Any] = ()) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    history = list(history or [])
    rejected_history = rejected_current = 0
    for item in items or []:
        if is_story_duplicate(item, history):
            rejected_history += 1
            continue
        if is_story_duplicate(item, accepted):
            rejected_current += 1
            continue
        accepted.append(dict(item))
    print(
        f"[Story Identity] history_duplicates={rejected_history} "
        f"current_run_duplicates={rejected_current} accepted={len(accepted)}",
        flush=True,
    )
    return accepted
