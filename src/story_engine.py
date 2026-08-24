"""Minimal, deterministic Story construction boundary for Radar 2.0."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime
from typing import Sequence

from radar_models import SourceItem, Story

_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "از", "و", "در", "به", "با", "برای", "که", "این", "آن", "یک", "را",
}


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS}


def _fingerprint(item: SourceItem) -> str:
    payload = " ".join(part for part in (item.url, item.title, item.summary, item.description) if part)
    return hashlib.sha256(payload.strip().lower().encode("utf-8")).hexdigest()[:20]


def _similarity(a: SourceItem, b: SourceItem) -> float:
    a_tokens = _tokens(f"{a.title} {a.summary} {a.description}")
    b_tokens = _tokens(f"{b.title} {b.summary} {b.description}")
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def _earliest(items: Sequence[SourceItem]) -> datetime | None:
    dates = [item.published_at for item in items if item.published_at]
    return min(dates) if dates else None


def _latest(items: Sequence[SourceItem]) -> datetime | None:
    dates = [item.published_at for item in items if item.published_at]
    return max(dates) if dates else None


def build_stories(items: Sequence[SourceItem], similarity_threshold: float = 0.58) -> list[Story]:
    """Cluster normalized SourceItems into deterministic canonical Story objects.

    This is a migration-safe lexical baseline. A later semantic clusterer can
    replace it behind this same API without changing production callers.
    """
    if not items:
        return []

    normalized = [item for item in items if item.url or item.title]
    by_url: dict[str, list[SourceItem]] = defaultdict(list)
    for item in normalized:
        by_url[item.url.strip().lower()].append(item)

    clusters: list[list[SourceItem]] = []
    for bucket in by_url.values():
        placed = False
        for existing in clusters:
            if any(
                _similarity(item, candidate) >= similarity_threshold
                for item in bucket
                for candidate in existing
            ):
                existing.extend(bucket)
                placed = True
                break
        if not placed:
            clusters.append(list(bucket))

    stories: list[Story] = []
    for cluster in clusters:
        canonical = max(
            cluster,
            key=lambda item: (
                1 if item.source_type in {"official", "primary"} else 0,
                len(item.title or ""),
                item.published_at or datetime.min,
            ),
        )
        story_id = hashlib.sha256(
            "|".join(sorted({_fingerprint(item) for item in cluster})).encode("utf-8")
        ).hexdigest()[:20]
        stories.append(
            Story(
                story_id=story_id,
                canonical_title=canonical.title,
                first_seen_at=_earliest(cluster),
                last_seen_at=_latest(cluster),
                people=sorted({p for item in cluster for p in item.people}),
                organizations=sorted({o for item in cluster for o in item.organizations}),
                topics=sorted({topic for item in cluster for topic in item.metadata.get("topics", []) if topic}),
                content_types=sorted({item.content_type for item in cluster if item.content_type}),
                sources=list(cluster),
                metadata={"cluster_size": len(cluster)},
            )
        )
    return stories
