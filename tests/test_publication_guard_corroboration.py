import json

import src.publication_guard as publication_guard


def _write_ledger(tmp_path, records):
    path = tmp_path / "telegram_feedback.json"
    path.write_text(json.dumps({"version": 2, "messages": {str(i): record for i, record in enumerate(records)}}, ensure_ascii=False), encoding="utf-8")
    publication_guard.LEDGER_PATH = path


def test_duplicate_requires_event_and_anchor_corroboration():
    old = {
        "title": "OpenAI launches GPT-6 Astra for work",
        "summary": "OpenAI launches GPT-6 Astra, a new model for workplace tasks.",
    }
    same_event = {
        "title": "OpenAI announces GPT-6 Astra workplace launch",
        "summary": "OpenAI announces GPT-6 Astra for workplace use.",
    }
    unrelated_openai = {
        "title": "OpenAI discusses a new research partnership in robotics",
        "summary": "OpenAI discusses robotics research and deployment with partners.",
    }
    duplicate_score = publication_guard._semantic_conflict(same_event["title"], same_event["summary"], old)
    unrelated_score = publication_guard._semantic_conflict(unrelated_openai["title"], unrelated_openai["summary"], old)
    assert duplicate_score >= 0.82
    assert unrelated_score < 0.82


def test_high_semantic_similarity_without_event_corroboration_is_not_enough():
    old = {
        "title": "NVIDIA research explores efficient AI hardware deployment",
        "summary": "NVIDIA research explores efficient AI hardware deployment and system design.",
    }
    different_event = {
        "title": "NVIDIA announces a new robotics investment program",
        "summary": "NVIDIA announces funding for robotics startups and deployment partnerships.",
    }
    score = publication_guard._semantic_conflict(different_event["title"], different_event["summary"], old)
    assert score < 0.82


def test_cross_source_same_event_with_one_concrete_anchor_is_blocked():
    old = {
        "title": "Sam Altman warns that AI power needs stronger safeguards",
        "summary": "Sam Altman warned at a public event that the growing power of AI requires stronger safeguards.",
    }
    rewritten = {
        "title": "Sam Altman says the growing power of AI requires safeguards",
        "summary": "At another report of the same remarks, Sam Altman said AI power requires stronger safeguards.",
    }
    score = publication_guard._semantic_conflict(rewritten["title"], rewritten["summary"], old)
    assert score >= 0.82


def test_same_person_different_event_remains_publishable():
    old = {
        "title": "Sam Altman warns that AI power needs stronger safeguards",
        "summary": "Sam Altman warned at a public event that the growing power of AI requires stronger safeguards.",
    }
    different_event = {
        "title": "Sam Altman discusses OpenAI's plans for new AI agents",
        "summary": "Sam Altman discussed a separate product direction involving autonomous AI agents.",
    }
    score = publication_guard._semantic_conflict(different_event["title"], different_event["summary"], old)
    assert score < 0.82


def test_cross_source_rewrite_is_blocked_by_publication_guard(tmp_path):
    _write_ledger(
        tmp_path,
        [{
            "title": "Dario Amodei calls for pacing frontier AI development",
            "summary": "Dario Amodei argues that frontier AI development should be paced to manage risks.",
            "link": "https://example.com/original",
        }],
    )
    allowed, reason = publication_guard.check_before_publish(
        "<b>📡 Dario Amodei urges pacing frontier AI development</b>\n"
        "<blockquote>📌 <b>خلاصه</b>\nDario Amodei argues that frontier AI development should be paced to manage risks.</blockquote>",
        "https://another.example/rewrite",
    )
    assert not allowed
    assert reason.startswith("semantic_story_already_published")

def test_observed_cross_source_ai_consciousness_rewrite_is_blocked():
    old = {
        "title": "آگاهی هوش مصنوعی ممکن است باعث ایجاد بزرگ‌ترین تقسیم اجتماعی بعدی شود",
        "summary": (
            "مصاحبه‌ای در مورد اینکه چگونه ظهور آگاهی در سیستم‌های هوش مصنوعی می‌تواند "
            "به عنوان یک عامل تقسیم‌کننده در جامعه عمل کند، مطرح شد. در این گفتگو، "
            "متخصصان به تأثیرات احتمالی بر عدالت، حریم خصوصی، و فرصت‌های شغلی اشاره کردند "
            "و هشدار دادند که بدون چارچوب‌های اخلاقی و قانونی مناسب، این فناوری می‌تواند "
            "نابرابری‌های موجود را تشدید کند."
        ),
    }
    rewritten = {
        "title": "چرا آگاهی هوش مصنوعی می‌تواند تقسیم‌ساز بزرگ جامعه شود",
        "summary": (
            "مقاله‌ای به بررسی این می‌پردازد که اگر هوش مصنوعی به‌گونه‌ای به‌نظر برسد "
            "که دارای آگاهی باشد، چگونه می‌تواند مرزهای جدیدی بین گروه‌های مختلف جامعه "
            "ایجاد کند و به اختلافات عمیق اجتماعی، حقوقی و فرهنگی منجر شود."
        ),
    }
    score = publication_guard._semantic_conflict(
        rewritten["title"], rewritten["summary"], old
    )
    assert score >= 0.82


def test_same_concept_but_materially_different_ai_consciousness_event_remains_publishable():
    old = {
        "title": "آگاهی هوش مصنوعی ممکن است باعث ایجاد بزرگ‌ترین تقسیم اجتماعی بعدی شود",
        "summary": "این گزارش درباره پیامدهای اجتماعی احتمالی آگاهی AI و اختلافات پیرامون حقوق آن است.",
    }
    different_event = {
        "title": "پژوهشگران آزمایش جدیدی برای سنجش نشانه‌های آگاهی در مدل‌های زبانی معرفی کردند",
        "summary": "یک مطالعه تجربی روش تازه‌ای برای آزمودن نشانه‌های آگاهی در مدل‌های زبانی پیشنهاد می‌کند.",
    }
    score = publication_guard._semantic_conflict(
        different_event["title"], different_event["summary"], old
    )
    assert score < 0.82
