"""Bounded parallel YouTube discovery adapter for production.

The legacy per-channel transport order is preserved:
Data API -> RSS -> public channel page. Only channel-level concurrency is
changed so one slow source cannot serialize the entire discovery stage.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fetch_youtube import (
    _fetch_channel_feed,
    _fetch_channel_page_items,
    _fetch_via_data_api,
    _normalize_video_result,
    _resolve_handle_to_channel_id,
    _youtube_api_key,
)

_DEFAULT_WORKERS = 6
_DEFAULT_BATCH_BUDGET_SECONDS = 240
_PRIORITY_TRANSCRIPT_CHANNELS = {
    "Lex Fridman Podcast",
    "Dwarkesh Patel",
    "No Priors Podcast",
    "Sean Carroll's Mindscape",
}
_DEFAULT_MAX_TRANSCRIPTS_PER_CHANNEL = 3


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _channel_workers() -> int:
    return _int_env("RADAR_YOUTUBE_WORKERS", _DEFAULT_WORKERS, 1, 8)


def _batch_budget() -> float:
    try:
        value = float(os.getenv("RADAR_YOUTUBE_DISCOVERY_SECONDS", str(_DEFAULT_BATCH_BUDGET_SECONDS)))
    except (TypeError, ValueError):
        value = _DEFAULT_BATCH_BUDGET_SECONDS
    return max(30.0, min(300.0, value))


def _max_transcripts() -> int:
    return _int_env(
        "RADAR_YOUTUBE_MAX_TRANSCRIPTS_PER_CHANNEL",
        _DEFAULT_MAX_TRANSCRIPTS_PER_CHANNEL,
        0,
        6,
    )


def _normalize_channel(channel: dict, item: dict, transcript_budget: int) -> dict | None:
    """Normalize one item while capping expensive transcript work per channel."""
    # _normalize_video_result performs transcript retrieval internally for a
    # small set of priority channels. Marking excess items as non-priority here
    # would change source metadata. Instead, callers only pass the newest N
    # entries to normalization for those channels.
    return _normalize_video_result(channel, item)


def _fetch_one_channel(channel: dict, cutoff: float, api_configured: bool) -> tuple[str, list[dict]]:
    started = time.monotonic()
    name = str(channel.get("name") or channel.get("channel_id") or "<unnamed>")
    channel_id = channel.get("channel_id")
    if not channel_id and channel.get("handle"):
        channel_id = _resolve_handle_to_channel_id(channel["handle"])
    if not channel_id:
        print(f"[WARN] YouTube channel {name!r} has no resolvable channel_id", flush=True)
        return name, []

    entries: list[dict] = []
    source_used = ""

    if api_configured:
        entries = _fetch_via_data_api(channel_id, name, cutoff) or []
        if entries:
            source_used = "data-api"

    if not entries:
        try:
            feed = _fetch_channel_feed(channel_id, name)
            for entry in list(getattr(feed, "entries", []) or []):
                published = entry.get("published_parsed")
                published_str = ""
                if published:
                    ts = time.mktime(published)
                    if ts < cutoff:
                        continue
                    published_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                entries.append(
                    {
                        "video_id": entry.get("yt_videoid", ""),
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": published_str,
                    }
                )
            if entries:
                source_used = "rss"
        except Exception as exc:
            print(f"[WARN] YouTube RSS failed for {name}: {exc}", flush=True)

    if not entries:
        entries = _fetch_channel_page_items(channel_id, name, cutoff) or []
        if entries:
            source_used = "channel-page"

    transcript_budget = _max_transcripts()
    if name in _PRIORITY_TRANSCRIPT_CHANNELS and transcript_budget >= 0:
        entries_to_normalize = entries[:transcript_budget] if transcript_budget else entries
        if transcript_budget == 0:
            # With zero, allow the existing description-only normalization to
            # run without transcript calls by temporarily using a non-priority
            # channel name only for this adapter's call surface.
            adapter_channel = dict(channel)
            adapter_channel["name"] = "__transcript_disabled__"
        else:
            adapter_channel = channel
    else:
        entries_to_normalize = entries
        adapter_channel = channel

    results: list[dict] = []
    for item in entries_to_normalize:
        normalized = _normalize_channel(adapter_channel, item, transcript_budget)
        if normalized:
            results.append(normalized)

    # If transcript work was deliberately capped, still retain remaining
    # videos with their original descriptions. They remain valid candidates;
    # only the optional transcript enrichment is skipped.
    if name in _PRIORITY_TRANSCRIPT_CHANNELS and transcript_budget > 0 and len(entries) > transcript_budget:
        description_only_channel = dict(channel)
        description_only_channel["name"] = "__transcript_disabled__"
        for item in entries[transcript_budget:]:
            normalized = _normalize_video_result(description_only_channel, item)
            if normalized:
                # Restore the canonical source identity after bypassing the
                # transcript trigger.
                normalized["source"] = f"YouTube - {name}"
                normalized["source_type"] = channel.get("type", "youtube")
                normalized["official"] = bool(channel.get("official", True))
                normalized["source_tier"] = channel.get("tier", 2)
                normalized["category"] = channel.get("category", "ai")
                results.append(normalized)

    elapsed = time.monotonic() - started
    print(f"[YouTube Source Timing] channel={name} source={source_used or 'unavailable'} elapsed={elapsed:.2f}s accepted={len(results)}", flush=True)
    return name, results


def fetch_youtube_items_parallel(youtube_channels, max_age_hours=72, ai_bridge_keywords=None):
    """Fetch monitored channels concurrently with a bounded production budget."""
    channels = list(youtube_channels or [])
    cutoff = time.time() - (min(max_age_hours, 720) * 3600)
    api_configured = bool(_youtube_api_key())
    workers = min(_channel_workers(), max(1, len(channels)))
    budget = _batch_budget()
    started = time.monotonic()
    print(
        f"[YouTube Discovery Parallel] api_key={'configured' if api_configured else 'not_configured'} "
        f"channels={len(channels)} workers={workers} budget={budget:.0f}s",
        flush=True,
    )
    if not channels:
        return []

    results: list[dict] = []
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="radar-youtube")
    futures = [executor.submit(_fetch_one_channel, channel, cutoff, api_configured) for channel in channels]
    try:
        deadline = time.monotonic() + budget
        for future in as_completed(futures, timeout=budget):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                _name, items = future.result(timeout=max(0.1, remaining))
                results.extend(items)
            except Exception as exc:
                print(f"[WARN] parallel YouTube worker failed: {exc}", flush=True)
    except TimeoutError:
        pending = sum(1 for future in futures if not future.done())
        print(f"[YouTube Discovery Parallel] budget_exhausted pending={pending}", flush=True)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    elapsed = time.monotonic() - started
    print(
        f"[YouTube Discovery Timing] parallel=true channels={len(channels)} workers={workers} "
        f"items={len(results)} elapsed={elapsed:.2f}s budget={budget:.0f}s",
        flush=True,
    )
    return results
