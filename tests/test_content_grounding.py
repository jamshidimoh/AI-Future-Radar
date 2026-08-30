import src.content_grounding as grounding


def test_source_grounding_blocks_topic_drift(monkeypatch):
    item = {
        "title": "Black Belt Speech | Lex Fridman",
        "summary": "Lex Fridman درباره دریافت کمربند مشکی، ریاضیات و تجربه شخصی خود صحبت می‌کند.",
    }
    draft = {
        "title": "Lex Fridman Podcast: بررسی‌های فنی و فلسفی در حوزه هوش مصنوعی",
        "summary": "این گفتگو درباره بررسی‌های فنی و فلسفی هوش مصنوعی است.",
        "why_it_matters": "این بحث مسیر آینده هوش مصنوعی را روشن می‌کند.",
        "category": "ai",
    }
    monkeypatch.setattr(grounding, "_llm_check", lambda *args, **kwargs: False)
    monkeypatch.setattr(grounding, "_repair", lambda *args, **kwargs: None)
    assert grounding.ensure_source_grounding(draft, item) is None


def test_source_grounding_blocks_drift_even_if_llm_says_grounded(monkeypatch):
    item = {
        "title": "Tennis (:30)",
        "summary": "A short tennis clip showing a tennis rally and match play.",
    }
    draft = {
        "title": "قابلیت تبدیل سبک هنری تصاویر در ChatGPT Images",
        "summary": "ChatGPT Images قابلیت تبدیل سبک هنری تصاویر را معرفی می‌کند.",
        "why_it_matters": "این قابلیت ویرایش تصویر را برای کاربران ساده‌تر می‌کند.",
        "category": "ai",
    }
    monkeypatch.setattr(grounding, "_llm_check", lambda *args, **kwargs: True)
    assert grounding.ensure_source_grounding(draft, item) is None


def test_source_grounding_accepts_supported_draft(monkeypatch):
    item = {
        "title": "This is the new ChatGPT Voice, powered by GPT-Live",
        "summary": "OpenAI در این ویدئو قابلیت صوتی جدید ChatGPT و تعامل طبیعی‌تر در حالت صوتی را معرفی می‌کند.",
    }
    draft = {
        "title": "معرفی صدای جدید ChatGPT با قدرت GPT-Live",
        "summary": "OpenAI قابلیت صوتی جدید ChatGPT را معرفی می‌کند که برای گفت‌وگوی طبیعی‌تر طراحی شده است.",
        "why_it_matters": "این تغییر تجربه تعامل صوتی با دستیارهای هوش مصنوعی را بهبود می‌دهد.",
        "category": "ai",
    }
    monkeypatch.setattr(grounding, "_llm_check", lambda *args, **kwargs: True)
    result = grounding.ensure_source_grounding(draft, item)
    assert result is draft
    assert result["source_grounding_verified"] is True


def test_source_grounding_repair_is_revalidated(monkeypatch):
    item = {
        "title": "Black Belt Speech | Lex Fridman",
        "summary": "Lex Fridman درباره تجربه دریافت کمربند مشکی و درس‌هایی که از سال‌ها تمرین گرفته صحبت می‌کند.",
    }
    draft = {
        "title": "Lex Fridman درباره یک تجربه",
        "summary": "موضوع اولیه به‌درستی توضیح داده نشده است.",
        "why_it_matters": "این متن نیاز به بازنویسی دارد.",
        "category": "ai",
    }
    repaired = {
        "title": "سخنرانی Lex Fridman درباره دریافت کمربند مشکی",
        "summary": "Lex Fridman تجربه دریافت کمربند مشکی و درس‌های حاصل از تمرین را شرح می‌دهد.",
        "why_it_matters": "این تجربه درباره یادگیری و انضباط شخصی است.",
        "category": "ai",
    }
    monkeypatch.setattr(grounding, "_llm_check", lambda title, text, candidate: candidate == repaired)
    monkeypatch.setattr(grounding, "_repair", lambda *args, **kwargs: dict(repaired))
    result = grounding.ensure_source_grounding(draft, item)
    assert result is not None
    assert result["source_grounding_repaired"] is True
