import json

from src.summarize import _language_ok, _repair_persian_draft, _repair_persian_fields


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

    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
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


def test_field_level_recovery_can_repair_persian_body_after_full_draft_failure(monkeypatch):
    import src.summarize as summarize

    repaired = {
        "summary": "David Chalmers در این ویدئو درباره آزمون‌های مرتبط با آگاهی در سامانه‌های هوش مصنوعی صحبت می‌کند. بحث بر تمایز میان رفتار هوشمند و تجربه آگاهانه تمرکز دارد و به مسئله سنجش آگاهی در ماشین‌ها می‌پردازد.",
        "why_it_matters": "اهمیت این بحث در آن است که معیارهای عملکردی به‌تنهایی ممکن است برای تمایز هوش از آگاهی کافی نباشند. چنین تمایزی می‌تواند بر نحوه طراحی آزمون‌های آینده برای سامانه‌های هوشمند و تفسیر ادعاهای مربوط به آگاهی ماشین اثر بگذارد.",
    }
    monkeypatch.setattr(
        summarize,
        "call_llm_with_fallback",
        lambda *args, **kwargs: (__import__("json").dumps(repaired, ensure_ascii=False), "test-provider"),
    )
    original = {
        "title": "David Chalmers: Tests for Consciousness in AI Systems",
        "summary": "An English summary.",
        "why_it_matters": "An English explanation.",
        "category": "mind",
    }
    candidate, provider = _repair_persian_fields(
        original,
        {
            "title": original["title"],
            "summary": "David Chalmers discusses tests for consciousness in AI systems and the problem of distinguishing intelligent behavior from conscious experience.",
            "category": "mind",
        },
        providers=[("test-provider", lambda *args, **kwargs: __import__("json").dumps(repaired, ensure_ascii=False))],
    )
    assert provider == "test-provider"
    assert "در این ویدئو" in candidate["summary"]
    assert "اهمیت این بحث" in candidate["why_it_matters"]


def test_length_gate_attempts_bounded_editorial_repair_before_reject(monkeypatch):
    import src.summarize as summarize

    short = {
        "title": "حل معمای آگاهی",
        "summary": "پژوهشگران درباره سنجش آگاهی در هوش مصنوعی و تفاوت آن با رفتار هوشمند بحث می‌کنند.",
        "why_it_matters": "این بحث برای طراحی آزمون‌های دقیق‌تر درباره آگاهی ماشین اهمیت دارد.",
        "speakers": "",
        "key_quote": "",
        "category": "mind",
    }
    repaired = {
        "title": "حل معمای آگاهی در سامانه‌های هوش مصنوعی",
        "summary": "پژوهشگران درباره سنجش آگاهی در سامانه‌های AI و تفاوت آن با رفتار هوشمند بحث می‌کنند. تمرکز اصلی بر معیارهایی است که بتوانند تجربه آگاهانه را از صرفاً عملکرد درست سامانه جدا کنند. این تمایز برای تفسیر ادعاهای مربوط به آگاهی ماشین در بحث 2023 اهمیت دارد و نشان می‌دهد آزمون‌های رفتاری به‌تنهایی ممکن است کافی نباشند.",
        "why_it_matters": "تفاوت میان عملکرد هوشمند و تجربه آگاهانه می‌تواند طراحی آزمون‌های آینده برای سامانه‌های AI را تغییر دهد. در صورتی که معیارهای فعلی فقط رفتار قابل مشاهده را بسنجند، ممکن است میان موفقیت وظیفه و وجود تجربه آگاهانه خلط ایجاد شود. بنابراین ارزیابی‌های آینده باید سازوکار و شواهد مستقل‌تری برای این دو مفهوم را با توجه به بحث 2023 در نظر بگیرند.",
        "speakers": "",
        "key_quote": "",
        "category": "mind",
    }
    calls = {"n": 0}

    def fake_call(*args, **kwargs):
        calls["n"] += 1
        payload = short if calls["n"] == 1 else repaired
        return json.dumps(payload, ensure_ascii=False), "test-provider"

    monkeypatch.setattr(summarize, "call_llm_with_fallback", fake_call)
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: [("test-provider", lambda *a, **k: json.dumps(repaired, ensure_ascii=False))])
    monkeypatch.setenv("AI_RADAR_EDITORIAL_REVIEW", "0")

    item = {
        "title": "Solving the mystery of consciousness",
        "summary": "This source discusses AI consciousness and distinguishes intelligent behavior from conscious experience in the 2023 debate. " * 10,
        "source": "The Economist",
        "category": "mind",
        "mission_area": "mind_cognition",
        "link": "https://example.invalid/mind",
    }
    result = summarize.summarize_item(item)
    assert result is not None
    assert len(result["summary"]) >= 180
    assert len(result["why_it_matters"]) >= 140
    assert calls["n"] >= 2


def test_mission_language_repair_chain_prioritizes_omniroute_and_audited_ollama(monkeypatch):
    import src.summarize as summarize

    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "1")
    monkeypatch.setattr(
        summarize,
        "get_quality_chain",
        lambda: [("test-provider", lambda *args, **kwargs: "{}")],
    )

    chain = summarize._language_repair_providers({"_mission_recovery_attempt": True})
    assert [name for name, _ in chain[:2]] == [
        "OmniRoute:mission-persian-repair",
        "OllamaLocal:qwen3:1.7b:mission-persian-repair",
    ]


def test_normal_language_repair_keeps_canonical_chain(monkeypatch):
    import src.summarize as summarize

    expected = [("test-provider", lambda *args, **kwargs: "{}")]
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: expected)
    assert summarize._language_repair_providers({}) is expected


def test_mission_recovery_initial_summary_uses_mission_provider_chain(monkeypatch):
    import src.summarize as summarize

    sentinel = [("mission-provider", lambda *args, **kwargs: "ignored")]
    calls = {}
    payload = {
        "title": "خبر تازه هوش مصنوعی",
        "summary": "این خبر درباره یک سامانه هوش مصنوعی جدید و روش ارزیابی آن است. پژوهشگران نتایج یک آزمون مشخص را گزارش کرده‌اند.",
        "why_it_matters": "نتیجه این آزمون می‌تواند نحوه ارزیابی سامانه‌های هوش مصنوعی را دقیق‌تر کند و محدودیت‌های روش فعلی را آشکار سازد.",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }

    def fake_call(*args, **kwargs):
        calls["providers"] = kwargs.get("providers")
        return json.dumps(payload, ensure_ascii=False), "mission-provider"

    monkeypatch.setattr(summarize, "_language_repair_providers", lambda _item: sentinel)
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: [("canonical-provider", lambda *a, **k: "ignored")])
    monkeypatch.setattr(summarize, "call_llm_with_fallback", fake_call)
    monkeypatch.setattr(summarize, "_language_ok", lambda _data: True)
    monkeypatch.setattr(summarize, "_length_ok", lambda _data, _source: True)
    monkeypatch.setattr(summarize, "_value_ok", lambda _data, _source: True)
    monkeypatch.setattr(summarize, "_run_shadow_claim_verification", lambda data, _item, _source: data)
    monkeypatch.setenv("AI_RADAR_EDITORIAL_REVIEW", "0")

    result = summarize.summarize_item({
        "title": "Fresh AI story",
        "summary": "The source describes a new AI system and a specific evaluation test.",
        "source": "Nature",
        "category": "ai",
        "mission_area": "ai_core",
        "link": "https://example.invalid/mission",
        "_mission_recovery_attempt": True,
    })
    assert result is not None
    assert calls["providers"] is sentinel
