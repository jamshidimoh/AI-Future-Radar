from src.summarize import _language_ok


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
