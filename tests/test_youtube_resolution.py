import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fetch_youtube import _resolve_handle_to_channel_id, _fetch_channel_feed


class YouTubeResolutionTests(unittest.TestCase):
    def test_known_channels_resolve_without_html_scraping(self):
        self.assertEqual(_resolve_handle_to_channel_id("@80000Hours"), "UCafjal1QYJ3rb0Y9xZk1Ezg")
        self.assertEqual(_resolve_handle_to_channel_id("@eightythousandhours"), "UCafjal1QYJ3rb0Y9xZk1Ezg")
        self.assertEqual(_resolve_handle_to_channel_id("@instituteofartandideas"), "UCTsiZiMomJo6FOyiBaFeaIw")

    @patch("fetch_youtube.requests.Session")
    def test_current_handle_fallback_resolves_channel_id(self, mock_session_cls):
        session = Mock()
        response = Mock(status_code=200, text='{"channelId":"UC1234567890123456789012"}')
        session.get.return_value = response
        mock_session_cls.return_value = session
        self.assertEqual(_resolve_handle_to_channel_id("@futureoflifeinstitute-test"), "UC1234567890123456789012")

    @patch("fetch_youtube.time.sleep")
    @patch("fetch_youtube.requests.get")
    def test_feed_fetch_uses_bounded_http_and_retries(self, mock_get, _sleep):
        first = Mock()
        first.status_code = 503
        first.raise_for_status.side_effect = RuntimeError("503")
        second = Mock()
        second.status_code = 200
        second.content = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test</title></entry></feed>'
        second.raise_for_status.return_value = None
        mock_get.side_effect = [first, second]

        feed = _fetch_channel_feed("UCafjal1QYJ3rb0Y9xZk1Ezg", "80,000 Hours")
        self.assertIsNotNone(feed)
        self.assertEqual(mock_get.call_count, 2)
        for call in mock_get.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 15)


if __name__ == "__main__":
    unittest.main()
