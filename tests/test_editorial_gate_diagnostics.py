"""Diagnostic-only regression coverage for editorial gate failures.

This test intentionally does not change production gate behavior. It verifies
that the two common cross-language requirements remain explicit: valid Persian
editorial copy must not be rejected merely because the source is English, while
unsupported generic impact copy remains rejected.
"""
from editorial_quality_policy import editorial_value_ok


def test_cross_language_valid_draft_is_accepted():
    source = (
        "OpenAI agents interacted with Hugging Face repositories and an agent "
        "was observed making changes. The report describes how the agents used "
        "tools and what happened during the incident."
    )
    summary = (
        "عامل‌های هوشمند OpenAI در تعامل با مخازن Hugging Face توانستند با ابزارهای "
        "نرم‌افزاری کار کنند و در جریان این تعامل تغییراتی ایجاد شد. این گزارش "
        "جزئیات رفتار عامل و نحوه استفاده آن از ابزارها را توضیح می‌دهد."
    )
    why = (
        "این رخداد برای توسعه عامل‌های خودکار اهمیت دارد، زیرا نشان می‌دهد "
        "استقرار چنین سیستم‌هایی می‌تواند ریسک تغییرات ناخواسته در محیط‌های واقعی "
        "را افزایش دهد و نیاز به ارزیابی و کنترل دقیق‌تر دارد."
    )
    assert editorial_value_ok("عامل‌های OpenAI و Hugging Face", summary, why, source)


def test_unsupported_generic_why_remains_rejected():
    source = "A research team published a technical result about a model."
    summary = "این پژوهش یک نتیجه فنی درباره مدل ارائه می‌کند و روش و نتیجه آزمایش را توضیح می‌دهد."
    why = "این پیشرفت می‌تواند آینده فناوری را تغییر دهد و اهمیت زیادی دارد."
    assert not editorial_value_ok("نتیجه پژوهش مدل", summary, why, source)
