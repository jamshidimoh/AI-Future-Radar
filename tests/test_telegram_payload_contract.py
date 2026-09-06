from src.send_telegram import TELEGRAM_TEXT_LIMIT, _chatgpt_link, format_post


def test_chatgpt_action_url_is_bounded():
    title = "معرفی یک مدل Multimodal جدید برای هوش مصنوعی"
    link = "https://example.com/source"
    url = _chatgpt_link(title, link)
    assert url.startswith("https://chatgpt.com/?q=")
    # Bound the action URL without imposing an arbitrary limit that can reject
    # perfectly usable UTF-8 encoded prompts by a few bytes.
    assert len(url) < 1250


def test_realistic_formatted_news_payload_fits_telegram():
    title = "معرفی یک مدل Multimodal جدید برای هوش مصنوعی"
    payload = format_post(
        {
            "title": title,
            "summary": "این یک خلاصه نسبتاً واقعی برای آزمون قرارداد انتشار است و باید بدون حذف ساختار اصلی در محدوده Telegram باقی بماند. " * 7,
            "why_it_matters": "این آزمون مطمئن می‌شود لینک اقدام ChatGPT باعث انفجار طول پیام نمی‌شود و خبر آماده انتشار باقی می‌ماند. " * 4,
            "_provider": "Groq:openai/gpt-oss-120b",
        },
        "Example Research Source",
        "https://example.com/source",
        published="2026-09-05",
    )
    assert payload
    assert len(payload) <= TELEGRAM_TEXT_LIMIT
