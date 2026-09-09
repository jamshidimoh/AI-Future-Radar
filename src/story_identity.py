"""Canonical story identity backed by the shared hybrid event matcher."""
from __future__ import annotations

import re
from typing import Any, Iterable
from canonical_story import canonical_url
from event_identity import compare_event_features, event_features, has_material_update
from semantic_dedup import get_story_signature, _similarity


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


def _prepare_prior(prior: Any) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None] | None:
    """Normalize one history/current item once for repeated pair comparisons."""
    if not isinstance(prior, dict):
        return None
    comparable = _coerce_prior(prior)
    if comparable is None:
        return None
    return comparable, _canonical_url(comparable), event_features(comparable), get_story_signature(comparable)


def _is_same_story_cached(
    candidate: dict[str, Any],
    candidate_url: str,
    candidate_features: dict[str, Any],
    candidate_signature: dict[str, Any],
    prior: tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None],
) -> bool:
    comparable, prior_url, prior_features, prior_signature = prior
    if candidate_url and prior_url and candidate_url == prior_url:
        return True
    if _is_protected_leader(candidate):
        return False
    kind, _, _ = compare_event_features(candidate_features, prior_features)
    if kind == "DUPLICATE":
        return True
    if kind == "UPDATE":
        return False
    if kind == "RELATED" and has_material_update(candidate, comparable):
        return False
    try:
        return _similarity(candidate_signature, prior_signature) >= 0.45
    except Exception:
        return False


def _build_comparison_cache(items: Iterable[Any]) -> list[tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None]]:
    cache = []
    for item in items or []:
        prepared = _prepare_prior(item)
        if prepared is not None:
            cache.append(prepared)
    return cache


def _is_story_duplicate_cached(
    candidate: dict[str, Any],
    cache: list[tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None]],
) -> bool:
    candidate_url = _canonical_url(candidate)
    candidate_features = event_features(candidate)
    candidate_signature = get_story_signature(candidate)
    return any(
        _is_same_story_cached(candidate, candidate_url, candidate_features, candidate_signature, prior)
        for prior in cache
    )


def _is_same_story(candidate: dict[str, Any], prior: Any) -> bool:
    prepared = _prepare_prior(prior)
    if prepared is None:
        return False
    candidate_url = _canonical_url(candidate)
    candidate_features = event_features(candidate)
    candidate_signature = get_story_signature(candidate)
    return _is_same_story_cached(candidate, candidate_url, candidate_features, candidate_signature, prepared)


def is_story_duplicate(candidate: dict[str, Any], prior_stories: Iterable[Any]) -> bool:
    return _is_story_duplicate_cached(candidate, _build_comparison_cache(prior_stories))


def deduplicate_stories(items: Iterable[dict[str, Any]], history: Iterable[Any] = ()) -> list[dict[str, Any]]:
    """Deduplicate with a precomputed history cache to avoid O(items*history) re-parsing."""
    accepted: list[dict[str, Any]] = []
    rejected_history = rejected_current = 0
    history_cache = _build_comparison_cache(history)
    accepted_cache: list[tuple[dict[str, Any], str, dict[str, Any], dict[str, Any] | None]] = []

    for item in items or []:
        if _is_story_duplicate_cached(item, history_cache):
            rejected_history += 1
            continue
        if _is_story_duplicate_cached(item, accepted_cache):
            rejected_current += 1
            continue
        accepted.append(dict(item))
        prepared = _prepare_prior(item)
        if prepared is not None:
            accepted_cache.append(prepared)

    print(f"[Story Identity] history_duplicates={rejected_history} current_run_duplicates={rejected_current} accepted={len(accepted)}", flush=True)
    return accepted
