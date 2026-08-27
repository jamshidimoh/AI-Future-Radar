"""Single publication contract for candidate identity, payload safety, and delivery outcomes.

This module is the narrow boundary between editorial orchestration and the
transport layer. It does not perform a second dedup pass; it centralizes the
invariants that must hold immediately before a Telegram publication request.
"""
from __future__ import annotations

from typing import Iterable

from canonical_story import canonical_url, normalize_title
from delivery_contract import DeliveryOutcome, from_legacy

TELEGRAM_SAFE_TEXT_LIMIT = 3900


def candidate_identity(item: dict) -> str:
    """Return the strongest stable identity available for one publication candidate."""
    url = canonical_url(item.get("canonical_url") or item.get("link") or item.get("url"))
    if url:
        return f"url:{url}"
    title = normalize_title(item.get("title", ""))
    if title:
        return f"title:{title}"
    leader = normalize_title(item.get("leader") or item.get("watch_person") or "")
    return f"leader:{leader}" if leader else f"object:{id(item)}"


def unique_candidates(items: Iterable[dict]) -> list[dict]:
    """Stable de-duplication before summarization/publication."""
    result: list[dict] = []
    seen: set[str] = set()
    for raw in items or []:
        item = dict(raw)
        key = candidate_identity(item)
        if key in seen:
            print(f"[Publication Contract] duplicate candidate removed identity={key}", flush=True)
            continue
        seen.add(key)
        item["publication_identity"] = key
        result.append(item)
    return result


def validate_publication_payload(post: object, *, content_type: str = "news") -> tuple[bool, str]:
    """Enforce the one-story/one-message payload boundary before transport.

    The production renderer deliberately uses a conservative 3900-character
    ceiling below Telegram's 4096-character text limit. Oversized content is
    rejected rather than chunked or retried through another delivery shape.
    """
    text = str(post or "")
    if not text.strip():
        return False, "empty_payload"
    if len(text) > TELEGRAM_SAFE_TEXT_LIMIT:
        return False, f"oversized_payload:{len(text)}>{TELEGRAM_SAFE_TEXT_LIMIT}"
    return True, "ok"


def delivery_result(result: object) -> dict:
    """Compatibility adapter for the current production wrapper."""
    outcome: DeliveryOutcome = from_legacy(result)
    return outcome.as_dict()
