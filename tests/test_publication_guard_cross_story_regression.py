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


def test_same_persian_story_rewrite_from_different_sources_is_blocked(tmp_path):
    published = {
        "title": "آگاهی هوش مصنوعی ممکن است باعث ایجاد بزرگ‌ترین تقسیم اجتماعی بعدی شود",
        "summary": "مصاحبه‌ای در مورد اینکه چگونه ظهور آگاهی در سیستم‌های هوش مصنوعی می‌تواند به عنوان یک عامل تقسیم‌کننده در جامعه عمل کند، مطرح شد. در این گفتگو، متخصصان به تأثیرات احتمالی بر عدالت، حریم خصوصی، و فرصت‌های شغلی اشاره کردند و هشدار دادند که بدون چارچوب‌های اخلاقی و قانونی مناسب، این فناوری می‌تواند نابرابری‌های موجود را تشدید کند.",
        "link": "https://example.com/down-to-earth",
    }
    candidate = _candidate(
        "چرا آگاهی هوش مصنوعی می‌تواند تقسیم‌ساز بزرگ جامعه شود",
        "مقالهٔ The Conversation به بررسی این می‌پردازد که اگر هوش مصنوعی به‌گونه‌ای به‌نظر برسد که دارای آگاهی باشد، چگونه می‌تواند مرزهای جدیدی بین گروه‌های مختلف جامعه ایجاد کند. نویسندگان استدلال می‌کنند که این مسأله نه تنها به‌مسئلهٔ اخلاقی و حقوقی می‌انجامد، بلکه می‌تواند باعث بروز اختلافات عمیق در سیاست، اقتصاد و فرهنگ شود.",
    )
    score = publication_guard._semantic_conflict(
        "چرا آگاهی هوش مصنوعی می‌تواند تقسیم‌ساز بزرگ جامعه شود",
        "مقالهٔ The Conversation به بررسی این می‌پردازد که اگر هوش مصنوعی به‌گونه‌ای به‌نظر برسد که دارای آگاهی باشد، چگونه می‌تواند مرزهای جدیدی بین گروه‌های مختلف جامعه ایجاد کند. نویسندگان استدلال می‌کنند که این مسأله نه تنها به‌مسئلهٔ اخلاقی و حقوقی می‌انجامد، بلکه می‌تواند باعث بروز اختلافات عمیق در سیاست، اقتصاد و فرهنگ شود.",
        published,
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/the-conversation", records=[published]
    )
    assert score >= 0.68
    assert not allowed
    assert reason.startswith("semantic_story_already_published")


def test_same_consciousness_anchor_different_event_remains_publishable(tmp_path):
    published = {
        "title": "آگاهی هوش مصنوعی و تقسیمات اجتماعی",
        "summary": "بحثی درباره پیامدهای اجتماعی تصور آگاهی در سیستم‌های هوش مصنوعی مطرح شد.",
        "link": "https://example.com/old-consciousness",
    }
    candidate = _candidate(
        "پژوهش درباره سنجش آگاهی در مدل‌های هوش مصنوعی",
        "یک پژوهش جدید روش‌های آزمایشی برای بررسی نشانه‌های آگاهی در مدل‌های هوش مصنوعی را بررسی می‌کند.",
    )
    allowed, reason = publication_guard.check_before_publish(
        candidate, "https://example.com/new-consciousness-research", records=[published]
    )
    assert allowed, reason
