import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import fetch_youtube


class YouTubeFallbackTests(unittest.TestCase):
    def test_known_handle_resolution_uses_stable_id(self):
        self.assertEqual(
            fetch_youtube._resolve_handle_to_channel_id("@80000Hours"),
            "UCafjal1QYJ3rb0Y9xZk1Ezg",
        )

    def test_yt_initial_data_page_fallback_extracts_video_metadata(self):
        html = '''<script id="ytInitialData">{"contents":{"videoRenderer":{"videoId":"AbCdEfGhijk","title":{"runs":[{"text":"AI future interview"}]},"publishedTimeText":{"simpleText":"2 hours ago"}}}}</script>'''
        response = Mock(status_code=200, text=html)
        with patch("fetch_youtube.requests.get", return_value=response):
            items = fetch_youtube._fetch_channel_page_items(
                "UC1234567890123456789012", "Test channel", 0
            )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "AI future interview")
        self.assertEqual(items[0]["video_id"], "AbCdEfGhijk")

    def test_data_api_returns_uploads_without_search_endpoint(self):
        channel_response = Mock()
        channel_response.raise_for_status = lambda: None
        channel_response.json.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        playlist_response = Mock()
        playlist_response.raise_for_status = lambda: None
        playlist_response.json.return_value = {
            "items": [{
                "contentDetails": {"videoId": "AbCdEfGhijk"},
                "snippet": {
                    "title": "AI safety interview",
                    "description": "description",
                    "publishedAt": "2026-08-15T08:00:00Z",
                },
            }]
        }
        with patch.dict("os.environ", {"YOUTUBE_API_KEY": "test-key"}), patch(
            "fetch_youtube.requests.get",
            side_effect=[channel_response, playlist_response],
        ):
            items = fetch_youtube._fetch_via_data_api(
                "UC1234567890123456789012", "Test channel", 0
            )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["video_id"], "AbCdEfGhijk")
        self.assertEqual(items[0]["title"], "AI safety interview")

    def test_fetch_uses_page_fallback_when_rss_fails(self):
        channel = {
            "name": "Test channel",
            "channel_id": "UC1234567890123456789012",
            "category": "ai",
            "tier": 1,
            "type": "interview",
            "content_type": "interview",
            "official": True,
        }
        with patch.dict("os.environ", {}, clear=False), patch(
            "fetch_youtube._fetch_channel_feed", side_effect=RuntimeError("404")
        ), patch(
            "fetch_youtube._fetch_channel_page_items",
            return_value=[{
                "title": "AI safety interview",
                "link": "https://www.youtube.com/watch?v=AbCdEfGhijk",
                "published": "2026-08-15 08:00",
                "video_id": "AbCdEfGhijk",
                "summary": "",
            }],
        ):
            items = fetch_youtube.fetch_youtube_items([channel], max_age_hours=72)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content_type"], "interview")
        self.assertEqual(items[0]["link"], "https://www.youtube.com/watch?v=AbCdEfGhijk")


if __name__ == "__main__":
    unittest.main()
