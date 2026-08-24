from src.editorial_quality_policy import (
    BODY_PERSIAN_RATIO_MIN,
    TITLE_PERSIAN_RATIO_MIN,
    length_ok,
    news_language_ok,
    normal_score_allowed,
)


def test_latin_product_name_is_allowed_in_persian_title():
    title = "معرفی Grok Bot برای تعامل مستقیم با کاربران"
    summary = "این خبر درباره معرفی یک قابلیت تازه است که در منبع توضیح داده شده و جزئیات فنی آن را ارائه می‌کند."
    why = "این تغییر می‌تواند بر تجربه کاربری و رقابت میان محصولات هوش مصنوعی اثر بگذارد."
    assert TITLE_PERSIAN_RATIO_MIN == 0.25
    assert news_language_ok(title, summary, why)


def test_body_language_gate_remains_strict():
    title = "معرفی Grok Bot"
    summary = "This is mostly English text and should not pass the Persian body gate."
    why = "This is also mostly English text."
    assert not news_language_ok(title, summary, why)
    assert BODY_PERSIAN_RATIO_MIN == 0.60


def test_compact_complete_summary_is_not_rejected_for_length():
    source = "الف" * 842
    summary = (
        "این خلاصه فارسی یک خبر را به‌صورت فشرده اما کامل توضیح می‌دهد؛ رویداد اصلی، "
        "نکته مهم منبع و نتیجه قابل برداشت را بیان می‌کند و اطلاعات ضروری برای انتشار "
        "خبری را بدون حاشیه‌گویی در اختیار مخاطب قرار می‌دهد."
    )
    why = (
        "اهمیت خبر در اثر آن بر رقابت و کاربردهای عملی هوش مصنوعی است و پیامد اصلی را "
        "روشن می‌کند. این اثر می‌تواند برای کاربران، شرکت‌ها و مسیر توسعه فناوری در "
        "کوتاه‌مدت و میان‌مدت قابل توجه باشد."
    )
    assert len(summary) >= 180
    assert len(why) >= 140
    assert length_ok(summary, why, source)


def test_normal_score_allows_controlled_step_down_from_high_baseline():
    assert normal_score_allowed(87.06, 88.0)
    assert not normal_score_allowed(84.9, 88.0)
    assert normal_score_allowed(87.97, 97.97)
    assert not normal_score_allowed(87.96, 97.97)


def test_low_baseline_uses_relative_tolerance_instead_of_impossible_floor():
    assert normal_score_allowed(76.9, 77.16)
    assert normal_score_allowed(70.0, 77.16)
    assert not normal_score_allowed(66.9, 77.16)
