import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from send_telegram import _chunk_text, _gregorian_date, _source_page_image, format_post
import telegram_single_delivery


class TelegramFormatTests(unittest.TestCase):
    def _plain(self, text):
        return text.replace("\u2067", "").replace("\u2066", "").replace("\u2069", "").replace("\u200f", "")

    def test_post_preserves_rtl_boxes_ltr_runs_and_title_hierarchy(self):
        title = "این یک عنوان فارسی نسبتاً طولانی است که باید پس از شکستن خط نیز راست‌چین باقی بماند"
        text = format_post({"title": title, "summary": "Demis Hassabis درباره DeepMind و آینده هوش مصنوعی صحبت می‌کند.", "why_it_matters": "این موضوع برای مسیر توسعه فناوری مهم است.", "key_quote": "", "category": "ai", "_provider": "Groq:qwen/qwen3.6-27b"}, "Google News (The Times of India)", "https://example.com/news", published="2026-08-13 10:30", content_type="news")
        plain = self._plain(text)
        for expected in ("مطالعه منبع اصلی", "بررسی بیشتر با ChatGPT", "Demis Hassabis", "Google News", "📡", title):
            self.assertIn(expected, plain)
        self.assertIn("<b>\u00a0📡", text)
        self.assertIn("<blockquote>📌 <b>خلاصه</b>", text)
        self.assertIn("<blockquote>💡 <b>چرا مهم است؟</b>", text)
        self.assertIn("\u2067", text)
        self.assertIn("\u2066", text)
        self.assertIn("\u2069", text)
        self.assertIn("\u200f", text)
        self.assertNotIn("\u202b", text)
        self.assertNotIn("\u202c", text)
        self.assertIn("<a href=\"", text)
        self.assertIn("<b>بررسی بیشتر با \u2066ChatGPT\u2069</b>", text)
        self.assertIn("\u2066🏛 Google News (The Times of India)\u2069", text)
        self.assertIn("🤖 \u2066Groq:qwen/qwen3.6-27b\u2069", text)
        self.assertIn("🗓 2026/08/13", text)

    def test_html_tags_are_not_corrupted_by_bidi_isolation(self):
        text = format_post({"title": "DeepMind: هوش مصنوعی", "summary": "خلاصه فارسی با ChatGPT", "why_it_matters": "اهمیت فناوری", "category": "ai"}, "Google News", "https://example.com/news")
        self.assertIn("<blockquote>📌 <b>خلاصه</b>", text)
        self.assertIn("<blockquote>💡 <b>چرا مهم است؟</b>", text)
        self.assertIn("<a href=\"", text)
        self.assertNotIn("<\u2066", text)
        self.assertNotIn("\u2069>", text)

    def test_title_contains_rtl_edge_markers_for_wrapped_lines(self):
        text = format_post({"title": "عنوان فارسی طولانی برای آزمون شکستن خط و حفظ راست‌چین بودن خط دوم", "summary": "خلاصه", "why_it_matters": "اهمیت", "category": "ai"}, "منبع", "https://example.com/news")
        title_line = text.splitlines()[0]
        self.assertTrue(title_line.startswith("\u2067<b>\u00a0📡\u200f"))
        self.assertTrue(title_line.endswith("\u200f</b>\u2069"))

    def test_source_page_image_reads_og_image_from_same_link(self):
        response = Mock(status_code=200, url="https://example.com/article", text='<html><meta property="og:image" content="https://example.com/images/article.jpg"></html>')
        with patch("send_telegram.requests.get", return_value=response):
            self.assertEqual(_source_page_image("https://example.com/article"), "https://example.com/images/article.jpg")

    def test_source_page_image_supports_relative_og_image(self):
        response = Mock(status_code=200, url="https://example.com/article", text='<meta property="og:image" content="/images/article.jpg">')
        with patch("send_telegram.requests.get", return_value=response):
            self.assertEqual(_source_page_image("https://example.com/article"), "https://example.com/images/article.jpg")

    def test_youtube_source_uses_video_thumbnail(self):
        self.assertEqual(_source_page_image("https://www.youtube.com/watch?v=AbCdEf12345"), "https://i.ytimg.com/vi/AbCdEf12345/hqdefault.jpg")

    def test_single_delivery_ignores_image_and_publishes_only_canonical_text(self):
        text_result = {"ok": True, "message_id": 123, "chat_id": -100123}
        with patch.object(telegram_single_delivery.send_telegram, "_telegram_preflight", return_value=True), \
             patch.object(telegram_single_delivery.send_telegram, "_send_text_full", return_value=text_result) as text_sender, \
             patch.object(telegram_single_delivery.send_telegram, "_send_source_image") as photo_sender, \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHANNEL": "-100123"}, clear=False):
            result = telegram_single_delivery.send("متن آزمون", image_url="https://example.com/image.jpg", source_link="https://example.com/article")
        self.assertEqual(result["message_id"], 123)
        self.assertIsNone(result["photo_message_id"])
        text_sender.assert_called_once_with("token", "-100123", "متن آزمون", preview_url="https://example.com/article", preflight=False)
        photo_sender.assert_not_called()

    def test_long_chatgpt_anchor_moves_to_keyboard_and_preserves_url(self):
        long_url = "https://chatgpt.com/?q=" + ("A" * 12000)
        text = '<a href="https://example.com/source">مطالعه منبع اصلی</a>\n\n<a href="' + long_url + '"><b>بررسی بیشتر با \u2066ChatGPT\u2069</b></a>'
        cleaned, extracted = telegram_single_delivery._extract_chatgpt_anchor(text)
        self.assertEqual(extracted, long_url)
        self.assertIn("<b>بررسی بیشتر با ChatGPT</b>", cleaned)
        self.assertNotIn(long_url, cleaned)

        response = Mock(status_code=200)
        response.json.return_value = {"ok": True, "result": {"message_id": 456, "chat": {"id": -100123}}}
        with patch.object(telegram_single_delivery.send_telegram, "_telegram_preflight", return_value=True), \
             patch("telegram_single_delivery.requests.post", return_value=response) as poster, \
             patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHANNEL": "-100123"}, clear=False):
            result = telegram_single_delivery._send_html_without_raw_length_guard(text, source_link="https://example.com/source")

        self.assertEqual(result["message_id"], 456)
        sent_data = poster.call_args.kwargs["data"]
        self.assertNotIn(long_url, sent_data["text"])
        self.assertIn("reply_markup", sent_data)
        self.assertIn(long_url, sent_data["reply_markup"])

    def test_long_content_is_chunked_without_truncation(self):
        text = "A" * 10000
        chunks = _chunk_text(text)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 4096 for chunk in chunks))

    def test_gregorian_date_parser(self):
        self.assertEqual(_gregorian_date("2026-08-13 10:30"), "2026/08/13")


if __name__ == "__main__":
    unittest.main()
