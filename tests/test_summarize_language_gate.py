from src.summarize import _language_ok, _repair_persian_draft


def test_language_gate_allows_persian_title_with_official_latin_name():
    data = {
        "title": "معرفی Grok Bot؛ دستیار جدید X.ai",
        "summary": "این شرکت از یک دستیار هوش مصنوعی جدید رونمایی کرده است که برای تعامل مستقیم با کاربران و اجرای وظایف متنی طراحی شده است.",
        "why_it_matters": "این تغییر می‌تواند رقابت میان دستیارهای هوش مصنوعی و محصولات مصرفی مبتنی بر مدل‌های زبانی را تشدید کند.",
    }
    assert _language_ok(data)


def test_language_gate_still_rejects_non_persian_summary():
    data = {
        "title": "معرفی Grok Bot؛ دستیار جدید X.ai",
        "summary": "This is an English-only summary with no Persian content.",
        "why_it_matters": "این خبر برای رقابت میان محصولات هوش مصنوعی مهم است و می‌تواند کاربردهای عملی جدیدی ایجاد کند.",
    }
    assert not _language_ok(data)


def test_full_draft_recovery_rejects_another_english_draft(monkeypatch):
    import src.summarize as summarize

    source = "این منبع درباره یک مدل جدید هوش مصنوعی و قابلیت‌های آن در استدلال و استفاده از ابزارها توضیح می‌دهد."
    original = {
        "title": "Gemini",
        "summary": "Google announced a new AI model with stronger reasoning and tool use.",
        "why_it_matters": "The model may change competition among frontier AI systems.",
        "category": "ai",
    }
    repaired = {
        "title": "مدل جدید Gemini برای استدلال و استفاده از ابزارها معرفی شد",
        "summary": "Google یک مدل جدید Gemini را معرفی کرده است که برای استدلال و استفاده از ابزارها بهبود یافته است.",
        "why_it_matters": "این پیشرفت می‌تواند رقابت میان مدل‌های پیشرفته هوش مصنوعی را تشدید کند و قابلیت‌های عامل‌محور را توسعه دهد.",
        "category": "ai",
    }
    monkeypatch.setattr(summarize, "call_llm_with_fallback", lambda *args, **kwargs: (__import__("json").dumps(repaired, ensure_ascii=False), "test-provider"))
    candidate, provider = _repair_persian_draft(original, {"summary": source, "category": "ai"})
    assert provider == "test-provider"
    assert candidate["title"].startswith("مدل جدید Gemini")
    assert _language_ok(candidate)
