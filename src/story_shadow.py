"""Side-effect-free Story Engine shadow adapter for Radar 2.0."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from radar_models import SourceItem
from story_engine import build_stories


def _parse_datetime(value: Any) -> datetime | None:
    """Parse legacy timestamps into timezone-naive UTC for deterministic ordering."""
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    try:
        return [str(x).strip() for x in value if str(x).strip()]
    except TypeError:
        text = str(value).strip()
        return [text] if text else []


def source_item_from_legacy(item: dict[str, Any], index: int = 0) -> SourceItem:
    people = _strings(item.get("people"))
    leader = str(item.get("leader") or item.get("watch_person") or "").strip()
    if leader and leader not in people:
        people.insert(0, leader)

    return SourceItem(
        source_id=str(item.get("source_id") or item.get("source") or f"legacy-{index}"),
        source_name=str(item.get("source") or item.get("source_name") or "unknown"),
        url=str(item.get("canonical_url") or item.get("link") or item.get("url") or ""),
        title=str(item.get("title") or ""),
        summary=str(item.get("summary") or ""),
        description=str(item.get("description") or item.get("content") or ""),
        source_type=str(item.get("source_type") or item.get("type") or ""),
        content_type=str(item.get("content_type") or "news"),
        published_at=_parse_datetime(item.get("published_at") or item.get("published")),
        image_url=str(item.get("source_image") or item.get("image_url") or "") or None,
        people=people,
        organizations=_strings(item.get("organizations")),
        metadata={
            "topics": _strings(item.get("topics")),
            "legacy_canonical_url": item.get("canonical_url"),
            "legacy_content_type": item.get("content_type"),
        },
    )


def build_shadow_stories(items: Iterable[dict[str, Any]], similarity_threshold: float = 0.58):
    source_items = [source_item_from_legacy(item, index=i) for i, item in enumerate(items)]
    stories = build_stories(source_items, similarity_threshold=similarity_threshold)
    telemetry = {
        "input_items": len(source_items),
        "shadow_stories": len(stories),
        "reduction_ratio": (1.0 - len(stories) / len(source_items)) if source_items else 0.0,
        "cluster_sizes": sorted((len(story.sources) for story in stories), reverse=True),
    }
    return stories, telemetry
