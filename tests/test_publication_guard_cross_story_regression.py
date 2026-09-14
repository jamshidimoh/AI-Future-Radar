from src import publication_guard


def _candidate(title, summary):
    return (
        f"<b>{title}</b>\n"
        f"<blockquote>📌 <b>خلاصه</b>\n{summary}</blockquote>"
    )


def test_unrelated_openai_ipo_and_model_launch_are_not_same_story():
    published = {
        "title": "Sam Altman در واشنگتن حضور دارد؛ OpenAI مدل جدیدی از هوش مصنوعی را معرفی می‌کند",
        "summary": "OpenAI درباره یک مدل جدید هوش مصنوعی توضیح داده است.",
        "link": "https://example.com/model-launch",
    }
    candidate = _candidate(
        "Sam Altman says OpenAI going public in 2026 would be ‘ill-advised’",
        "Sam Altman says an OpenAI initial public offering in 2026 would be ill-advised.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/ipo", records=[published]
    )
    assert allowed, reason


def test_unrelated_womens_health_and_copper_infrastructure_stories_are_not_same_story():
    published = {
        "title": "رقابت جهانی برای تأمین مس؛ چالش‌های زیرساخت‌های انرژی آینده",
        "summary": "رقابت جهانی برای تأمین مس و زیرساخت‌های انرژی آینده شدت گرفته است.",
        "link": "https://example.com/copper",
    }
    candidate = _candidate(
        "The women’s health gap should not exist. Here’s how to close it",
        "The World Economic Forum examines the persistent gap in women's health and approaches to closing it.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/womens-health", records=[published]
    )
    assert allowed, reason


def test_unrelated_solar_railway_and_copper_infrastructure_stories_are_not_same_story():
    published = {
        "title": "رقابت جهانی برای تأمین مس؛ چالش‌های زیرساخت‌های انرژی آینده",
        "summary": "رقابت جهانی برای تأمین مس و زیرساخت‌های انرژی آینده شدت گرفته است.",
        "link": "https://example.com/copper",
    }
    candidate = _candidate(
        "Switzerland’s Solar Railway & Closing Women’s Health Gap | WEF | Stories of the Week",
        "The WEF weekly stories cover a solar railway in Switzerland and progress on closing the women's health gap.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/wef-weekly", records=[published]
    )
    assert allowed, reason
