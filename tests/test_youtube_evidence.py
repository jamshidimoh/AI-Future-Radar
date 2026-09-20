from pathlib import Path
from unittest.mock import patch

from src.fetch_youtube import _normalize_video_result, _walk_video_renderers

ROOT = Path(__file__).resolve().parents[1]


# Regression coverage for YouTube channel-page evidence recovery.
def test_channel_renderer_keeps_structured_description_as_evidence():
    out = []
    payload = {
        "videoRenderer": {
            "videoId": "abcdefghijk",
            "title": {"runs": [{"text": "A future AI interview"}]},
            "publishedTimeText": {"simpleText": "1 day ago"},
            "detailedMetadataSnippets": [
                {"snippet": {"runs": [{"text": "This discussion covers artificial intelligence, agents and reasoning models."}]}}
            ],
        }
    }
    _walk_video_renderers(payload, out)
    assert out[0]["summary"]
    assert "artificial intelligence" in out[0]["summary"].lower()


def test_normalize_prefers_real_description_before_network_transcript():
    channel = {"name": "Test AI", "category": "ai", "tier": 1, "type": "podcast", "official": True}
    item = {
        "video_id": "abcdefghijk",
        "title": "Research on AI agents",
        "link": "https://www.youtube.com/watch?v=abcdefghijk",
        "summary": "Researchers evaluate AI agents and reasoning models.",
        "published": "2026-08-24 00:00",
    }
    result = _normalize_video_result(channel, item)
    assert result["summary"] == item["summary"]
    assert result["evidence_source"] == "channel_page_description"
    assert result["evidence_text"] == item["summary"]


def test_mind_focused_video_fetches_transcript_evidence_even_on_non_priority_channel():
    channel = {"name": "Test Ideas Forum", "category": "ai", "tier": 1, "type": "talk", "official": True}
    item = {
        "video_id": "abcdefghijk",
        "title": "David Chalmers: Tests for Consciousness in AI Systems",
        "link": "https://www.youtube.com/watch?v=abcdefghijk",
        "summary": "",
        "published": "2026-09-20 00:00",
    }
    with patch(
        "src.fetch_youtube._get_transcript_snippet",
        return_value="Chalmers discusses consciousness tests for artificial intelligence systems.",
    ) as mocked:
        result = _normalize_video_result(channel, item)
    mocked.assert_called_once_with("abcdefghijk")
    assert "Chalmers discusses consciousness tests" in result["evidence_text"]
    assert result["evidence_source"] == "transcript"


def test_generic_ai_video_does_not_trigger_thematic_mind_transcript():
    channel = {"name": "Test AI", "category": "ai", "tier": 1, "type": "talk", "official": True}
    item = {
        "video_id": "abcdefghijk",
        "title": "New AI model launch",
        "link": "https://www.youtube.com/watch?v=abcdefghijk",
        "summary": "A new model launch and benchmark update.",
        "published": "2026-09-20 00:00",
    }
    with patch(
        "src.fetch_youtube._get_transcript_snippet",
        return_value="should not be used",
    ) as mocked:
        result = _normalize_video_result(channel, item)
    mocked.assert_not_called()
    assert result["evidence_source"] == "channel_page_description"


def test_mind_video_uses_video_page_evidence_when_transcript_unavailable():
    channel = {"name": "Test Ideas Forum", "category": "ai", "tier": 1, "type": "talk", "official": True}
    item = {
        "video_id": "abcdefghijk",
        "title": "David Chalmers: Tests for Consciousness in AI Systems",
        "link": "https://www.youtube.com/watch?v=abcdefghijk",
        "summary": "",
        "published": "2026-09-20 00:00",
    }
    with patch(
        "src.fetch_youtube._get_transcript_snippet",
        return_value="",
    ), patch(
        "src.fetch_youtube._fetch_video_page_evidence",
        return_value="This talk examines tests for consciousness in AI systems and phenomenal concepts.",
    ) as mocked:
        result = _normalize_video_result(channel, item)
    mocked.assert_called_once_with("abcdefghijk")
    assert "phenomenal concepts" in result["evidence_text"]
    assert result["evidence_source"] == "video_page"
