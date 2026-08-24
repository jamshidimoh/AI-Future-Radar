import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fetch_youtube import _normalize_video_result, _walk_video_renderers


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
