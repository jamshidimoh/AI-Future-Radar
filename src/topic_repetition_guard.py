"""History-aware topic repetition guard for editorial publication.

This guard is intentionally separate from same-story deduplication. It prevents
different URLs that are materially about the same recent topic from crowding the
feed, while leaving genuinely new developments eligible.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.event_identity import has_material_update
from src.semantic_dedup import _similarity, get_story_signature


def _signature(value: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(value, dict):
        return get_story_signature(value)
    return get_story_signature(str(value or ""))


def _anchor_overlap(left: dict[str, Any], right: dict[str, Any]) -> int:
    return len(set(left.get("anchors") or []) & set(right.get("anchors") or []))


def _topic_score(item: dict[str, Any], prior: dict[str, Any] | str) -> tuple[float, int]:
    candidate = get_story_signature(item)
    stored = _signature(prior)
    return _similarity(candidate, stored), _anchor_overlap(candidate, stored)


def find_topic_repetition(
    item: dict[str, Any],
    history: Iterable[dict[str, Any] | str],
    *,
    threshold: float = 0.68,
    soft_threshold: float = 0.62,
    min_anchor_overlap: int = 2,
) -> tuple[float, str]:
    """Return the strongest recent topic repetition score and matched title."""
    best_score = 0.0
    best_title = ""
    candidate = get_story_signature(item)
    for prior in history or ():
        score, anchors = _topic_score(item, prior)
        if score < soft_threshold or anchors < min_anchor_overlap:
            continue
        if score >= threshold:
            prior_title = str(_signature(prior).get("title_text") or "").strip()
            if score > best_score:
                best_score = score
                best_title = prior_title
    return best_score, best_title


def filter_history_topic_repetition(
    items: Iterable[dict[str, Any]],
    history: Iterable[dict[str, Any] | str],
    *,
    window: int = 24,
    threshold: float = 0.66,
    soft_threshold: float = 0.60,
    min_anchor_overlap: int = 1,
) -> tuple[list[dict[str, Any]], int]:
    """Remove normal candidates that substantially repeat a recently published topic."""
    materialized = list(items or ())
    recent = list(history or ())[-max(0, int(window)):] if window else []
    if not recent:
        return materialized, 0

    kept: list[dict[str, Any]] = []
    blocked = 0
    for item in materialized:
        score, matched = find_topic_repetition(
            item,
            recent,
            threshold=threshold,
            soft_threshold=soft_threshold,
            min_anchor_overlap=min_anchor_overlap,
        )
        if score >= threshold:
            comparable = next((
                prior for prior in recent
                if str(_signature(prior).get("title_text") or "").strip() == matched
            ), None)
            if comparable is not None:
                if isinstance(comparable, dict):
                    prior_item = comparable
                else:
                    prior_sig = _signature(comparable)
                    prior_item = {
                        "title": str(prior_sig.get("title_text") or matched),
                        "summary": " ".join(str(x) for x in (prior_sig.get("context") or [])),
                    }
                if has_material_update(item, prior_item):
                    kept.append(item)
                    continue
            blocked += 1
            print(
                "[Topic Repetition Guard] blocked "
                f"score={score:.3f} matched={matched[:100]} "
                f"title={str(item.get('title') or '')[:120]}",
                flush=True,
            )
            continue
        kept.append(item)

    print(
        "[Topic Repetition Guard] "
        f"checked={len(materialized)} blocked={blocked} remaining={len(kept)} "
        f"window={len(recent)} threshold={threshold:.2f}",
        flush=True,
    )
    return kept, blocked
