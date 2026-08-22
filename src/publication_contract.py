"""Single publication contract for candidate identity and delivery outcomes.

This module is the migration boundary between editorial orchestration and the
transport layer. It keeps candidate identity deterministic and normalizes
legacy delivery results into typed outcomes without adding another dedup layer.
"""
from __future__ import annotations

from typing import Iterable

from canonical_story import canonical_url, normalize_title
from delivery_contract import DeliveryOutcome, from_legacy


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


def delivery_result(result: object) -> dict:
    """Compatibility adapter for the current production wrapper.

    The public production path still consumes a dict today, while the typed
    DeliveryOutcome is introduced as the single migration boundary. Callers
    can therefore migrate without changing editorial semantics in this step.
    """
    outcome: DeliveryOutcome = from_legacy(result)
    return outcome.as_dict()
