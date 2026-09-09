import time
from unittest.mock import patch

import youtube_parallel_discovery as parallel


def _fake_feed(channel_id, channel_name):
    return type("Feed", (), {"entries": [{
        "yt_videoid": "abcdefghijk",
        "title": f"{channel_name} latest AI update",
        "summary": "AI evidence",
        "link": "https://youtube.com/watch?v=abcdefghijk",
        "published_parsed": None,
    }]})()


def _fake_normalize(channel, item):
    return {
        "title": item["title"],
        "link": item["link"],
        "source": f"YouTube - {channel['name']}",
    }


def test_parallel_discovery_runs_channels_concurrently(monkeypatch):
    channels = [
        {"name": "A", "channel_id": "UCA"},
        {"name": "B", "channel_id": "UCB"},
        {"name": "C", "channel_id": "UCC"},
        {"name": "D", "channel_id": "UCD"},
    ]
    active = {"count": 0, "peak": 0}

    def slow_feed(channel_id, channel_name):
        active["count"] += 1
        active["peak"] = max(active["peak"], active["count"])
        try:
            time.sleep(0.08)
            return _fake_feed(channel_id, channel_name)
        finally:
            active["count"] -= 1

    monkeypatch.setenv("RADAR_YOUTUBE_WORKERS", "4")
    monkeypatch.setenv("RADAR_YOUTUBE_DISCOVERY_SECONDS", "30")
    monkeypatch.setenv("RADAR_YOUTUBE_MAX_TRANSCRIPTS_PER_CHANNEL", "0")

    with (
        patch.object(parallel, "_youtube_api_key", return_value=""),
        patch.object(parallel, "_fetch_channel_feed", side_effect=slow_feed),
        patch.object(parallel, "_fetch_channel_page_items", return_value=[]),
        patch.object(parallel, "_normalize_video_result", side_effect=_fake_normalize),
    ):
        started = time.monotonic()
        result = parallel.fetch_youtube_items_parallel(channels, max_age_hours=72)
        elapsed = time.monotonic() - started

    assert len(result) == 4
    assert active["peak"] >= 2
    assert elapsed < 0.28
    assert {item["source"] for item in result} == {"YouTube - A", "YouTube - B", "YouTube - C", "YouTube - D"}


def test_transcript_cap_preserves_remaining_videos_without_transcripts(monkeypatch):
    channel = {
        "name": "Lex Fridman Podcast",
        "channel_id": "UCL",
        "category": "ai",
        "tier": 1,
        "type": "podcast",
        "content_type": "podcast",
        "official": True,
    }
    entries = [
        {
            "video_id": f"id{i:09d}"[-11:],
            "title": f"AI episode {i}",
            "summary": "description",
            "link": f"https://youtube.com/watch?v={i}",
            "published": "2026-09-09 07:00",
        }
        for i in range(4)
    ]
    normalize_calls = []

    def fake_normalize(ch, item):
        normalize_calls.append(ch["name"])
        return {"title": item["title"], "source": f"YouTube - {channel['name']}"}

    monkeypatch.setenv("RADAR_YOUTUBE_WORKERS", "1")
    monkeypatch.setenv("RADAR_YOUTUBE_MAX_TRANSCRIPTS_PER_CHANNEL", "2")
    monkeypatch.setenv("RADAR_YOUTUBE_DISCOVERY_SECONDS", "30")

    with (
        patch.object(parallel, "_youtube_api_key", return_value=""),
        patch.object(parallel, "_fetch_channel_feed", return_value=type("Feed", (), {"entries": []})()),
        patch.object(parallel, "_fetch_channel_page_items", return_value=entries),
        patch.object(parallel, "_normalize_video_result", side_effect=fake_normalize),
    ):
        result = parallel.fetch_youtube_items_parallel([channel], max_age_hours=720)

    assert len(result) == 4
    assert normalize_calls[:2] == ["Lex Fridman Podcast", "Lex Fridman Podcast"]
    assert normalize_calls[2:] == ["__transcript_disabled__", "__transcript_disabled__"]
