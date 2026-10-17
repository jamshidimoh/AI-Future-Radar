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


def test_naturalness_recovery_retries_full_draft_only_after_ratio_pass(monkeypatch):
    import src.summarize as summarize

    original = {
        "title": "مدل هوش مصنوعی معرفی شد",
        "summary": "متن فارسی اولیه با ساختار نامأنوس است و نیاز به بازنویسی کامل دارد.",
        "why_it_matters": "این روش برای ارزیابی مدل اهمیت دارد و محدودیت‌های آن باید دقیق توضیح داده شود.",
    }
    repaired = {
        **original,
        "summary": "پژوهشگران یک مدل هوش مصنوعی را معرفی کرده‌اند. ارزیابی آن بر چند آزمون مشخص تکیه دارد و نتایج، محدودیت‌هایی را در روش فعلی نشان می‌دهد.",
        "why_it_matters": "این نتیجه به مقایسه دقیق‌تر مدل‌ها کمک می‌کند. چون آزمون‌ها محدودیت دارند، برای تصمیم‌گیری عملی باید شواهد مستقل دیگری هم بررسی شود.",
    }
    calls = {"count": 0}
    monkeypatch.setattr(summarize, "news_language_ok", lambda *args: True)
    monkeypatch.setattr(summarize, "persian_editorial_naturalness_ok", lambda *args: False)
    def fake_repair(data, item):
        calls["count"] += 1
        return repaired, "test-provider"
    monkeypatch.setattr(summarize, "_repair_persian_draft", fake_repair)
    monkeypatch.setattr(summarize, "_language_ok", lambda data: data is repaired)

    result, provider = summarize._repair_persian_naturalness(original, {"title": "source"})

    assert result is repaired
    assert provider == "test-provider"
    assert calls["count"] == 1


def test_naturalness_recovery_fails_closed_when_full_draft_still_invalid(monkeypatch):
    import src.summarize as summarize

    original = {
        "title": "مدل هوش مصنوعی معرفی شد",
        "summary": "متن فارسی اولیه است.",
        "why_it_matters": "این روش اهمیت دارد.",
    }
    invalid_recovery = {**original, "summary": "متن بازنویسی‌شده هنوز نامعتبر است."}
    monkeypatch.setattr(summarize, "news_language_ok", lambda *args: True)
    monkeypatch.setattr(summarize, "persian_editorial_naturalness_ok", lambda *args: False)
    monkeypatch.setattr(summarize, "_repair_persian_draft", lambda data, item: (invalid_recovery, "test-provider"))
    monkeypatch.setattr(summarize, "_language_ok", lambda data: False)

    result, provider = summarize._repair_persian_naturalness(original, {"title": "source"})

    assert result is original
    assert provider == "test-provider"

def test_claim_alignment_recovery_rechecks_and_accepts_grounded_repair(monkeypatch):
    import src.summarize as summarize
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: [("test-provider", lambda *args, **kwargs: "")])

    repaired = {
        "title": "پژوهش تازه درباره ارزیابی مدل هوش مصنوعی",
        "summary": "پژوهشگران یک روش ارزیابی برای مدل هوش مصنوعی بررسی کرده‌اند. متن منبع روش و دامنه آزمون را توضیح می‌دهد. گزارش جزئیات مشخصی درباره ارزیابی ارائه می‌کند.",
        "why_it_matters": "این اطلاعات برای فهم دامنه آزمون و تفسیر نتیجه‌های گزارش‌شده کاربرد دارد. خواننده می‌تواند بر اساس جزئیات منبع، محدودیت‌های روش را بهتر بررسی کند. ادعای فراتر از شواهد در این توضیح مطرح نمی‌شود.",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    monkeypatch.setattr(
        summarize,
        "call_llm_with_fallback",
        lambda *args, **kwargs: (json.dumps(repaired, ensure_ascii=False), "test-provider"),
    )
    monkeypatch.setattr(summarize, "_language_ok", lambda _data: True)
    monkeypatch.setattr(summarize, "_length_ok", lambda _data, _source: True)
    monkeypatch.setattr(summarize, "_value_ok", lambda _data, _source: True)

    def verified(candidate, _item, _source):
        candidate["_claim_verification"] = {"status": "VERIFIED", "flags": []}
        return candidate

    monkeypatch.setattr(summarize, "_run_shadow_claim_verification", verified)
    candidate, provider = summarize._repair_claim_alignment(
        repaired,
        {"category": "ai", "title": "AI evaluation method"},
        "The source describes a method and the scope of a specific evaluation.",
        {"causal_overreach", "unsupported_superlative"},
    )
    assert provider == "test-provider"
    assert candidate is not None
    assert candidate["_claim_verification"]["flags"] == []
    assert candidate["_provider_claim_repair"] == "test-provider"


def test_claim_alignment_recovery_fails_closed_when_hard_flags_remain(monkeypatch):
    import src.summarize as summarize
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: [("test-provider", lambda *args, **kwargs: "")])

    repaired = {
        "title": "پژوهش درباره ارزیابی مدل هوش مصنوعی",
        "summary": "پژوهشگران یک روش ارزیابی برای مدل هوش مصنوعی بررسی کرده‌اند. متن منبع دامنه آزمون و جزئیات روش را شرح می‌دهد. گزارش اطلاعات مشخصی درباره این ارزیابی ارائه می‌کند.",
        "why_it_matters": "این جزئیات به فهم روش ارزیابی کمک می‌کند. تفسیر نتیجه‌ها باید به دامنه آزمون و محدودیت‌های گزارش توجه داشته باشد. توضیح حاضر ادعای قطعی دیگری اضافه نمی‌کند.",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    monkeypatch.setattr(
        summarize,
        "call_llm_with_fallback",
        lambda *args, **kwargs: (json.dumps(repaired, ensure_ascii=False), "test-provider"),
    )
    monkeypatch.setattr(summarize, "_language_ok", lambda _data: True)
    monkeypatch.setattr(summarize, "_length_ok", lambda _data, _source: True)
    monkeypatch.setattr(summarize, "_value_ok", lambda _data, _source: True)

    def still_unverified(candidate, _item, _source):
        candidate["_claim_verification"] = {
            "status": "VERIFIED",
            "flags": ["causal_overreach"],
        }
        return candidate

    monkeypatch.setattr(summarize, "_run_shadow_claim_verification", still_unverified)
    candidate, _provider = summarize._repair_claim_alignment(
        repaired,
        {"category": "ai", "title": "AI evaluation method"},
        "The source describes a method and the scope of a specific evaluation.",
        {"causal_overreach"},
    )
    assert candidate is None

def test_claim_alignment_recovery_fails_closed_when_provider_chain_unavailable(monkeypatch):
    import src.summarize as summarize

    def unavailable():
        raise RuntimeError("no credentialed provider")

    monkeypatch.setattr(summarize, "get_quality_chain", unavailable)
    candidate, provider = summarize._repair_claim_alignment(
        {
            "title": "عنوان فارسی",
            "summary": "خلاصه فارسی",
            "why_it_matters": "اهمیت فارسی",
        },
        {"category": "ai", "title": "Source title"},
        "Source evidence",
        {"causal_overreach"},
    )
    assert candidate is None
    assert provider is None



def test_claim_alignment_recovery_retries_once_for_contract_mismatch(monkeypatch):
    import src.summarize as summarize
    from src.llm_router_light import ProductionQualityChain

    initial = {
        "title": "پژوهش درباره مدل هوش مصنوعی",
        "summary": "draft",
        "why_it_matters": "draft",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    repaired = {
        "title": "ارزیابی مستند یک مدل هوش مصنوعی",
        "summary": "READY",
        "why_it_matters": "READY",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    responses = [
        (json.dumps(initial, ensure_ascii=False), "test-provider-a"),
        (json.dumps(repaired, ensure_ascii=False), "test-provider-b"),
    ]
    calls = []
    provider_chain = ProductionQualityChain([
        ("test-provider-a:model", lambda *args, **kwargs: ""),
        ("test-provider-b:model", lambda *args, **kwargs: ""),
    ])
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: provider_chain)

    def fake_call(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(summarize, "call_llm_with_fallback", fake_call)
    monkeypatch.setattr(summarize, "_language_ok", lambda candidate: candidate.get("summary") == "READY")
    monkeypatch.setattr(summarize, "_length_ok", lambda candidate, source: candidate.get("summary") == "READY")
    monkeypatch.setattr(summarize, "_value_ok", lambda candidate, source: candidate.get("summary") == "READY")

    def verified(candidate, _item, _source):
        candidate["_claim_verification"] = {"status": "VERIFIED", "flags": []}
        return candidate

    monkeypatch.setattr(summarize, "_run_shadow_claim_verification", verified)
    candidate, provider = summarize._repair_claim_alignment(
        initial,
        {"category": "ai", "title": "AI model evaluation"},
        "The source describes an AI model evaluation and its reported scope.",
        {"unsupported_comparison"},
    )

    assert len(calls) == 2
    assert "Persian language/naturalness/terminology" in calls[1][0][0]
    assert isinstance(calls[0][1]["providers"], ProductionQualityChain)
    assert type(calls[1][1]["providers"]) is list
    assert [name for name, _ in calls[1][1]["providers"]] == ["test-provider-b:model"]
    assert candidate is not None
    assert candidate["summary"] == "READY"
    assert provider == "test-provider-b"

def test_full_draft_repair_prompt_includes_specific_naturalness_feedback(monkeypatch):
    import src.summarize as summarize

    invalid = {
        "title": "پژوهش تازه درباره یک مدل هوش مصنوعی",
        "summary": "این سامانه میتواند داده‌ها را تحلیل کند و روش ارزیابی را با چند معیار بررسی کند. متن منبع جزئیات آزمون و دامنه پژوهش را گزارش می‌کند.",
        "why_it_matters": "این روش می‌تواند به مقایسه مدل‌ها کمک کند و محدودیت‌های ارزیابی را روشن‌تر سازد. تصمیم‌گیری عملی همچنان به شواهد مستقل نیاز دارد.",
        "category": "ai",
    }
    repaired = {
        "title": "پژوهش تازه درباره ارزیابی یک مدل هوش مصنوعی",
        "summary": "پژوهشگران یک مدل هوش مصنوعی را با چند معیار مشخص ارزیابی کرده‌اند. متن منبع دامنه آزمون و جزئیات روش را توضیح می‌دهد. نتایج گزارش‌شده برای فهم محدودیت‌های این ارزیابی اهمیت دارند.",
        "why_it_matters": "این جزئیات به مقایسه دقیق‌تر روش‌های ارزیابی کمک می‌کند. برای تصمیم‌گیری عملی باید دامنه آزمون و محدودیت‌های گزارش را در نظر گرفت. نتیجه‌گیری فراتر از شواهد موجود در منبع موجه نیست.",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    observed = {}
    provider_sentinel = [("test-provider", lambda *_args, **_kwargs: None)]

    def fake_call(prompt, user_content, providers=None):
        observed["prompt"] = prompt
        observed["user_content"] = user_content
        observed["providers"] = providers
        return json.dumps(repaired, ensure_ascii=False), "test-provider"

    monkeypatch.setattr(summarize, "_language_repair_providers", lambda _item: provider_sentinel)
    monkeypatch.setattr(summarize, "call_llm_with_fallback", fake_call)
    source = (
        "The source describes an artificial intelligence model and the criteria used to evaluate it. "
        "It specifies the scope of the test, the evaluation method, and limitations of the reported results. "
    ) * 4
    candidate, provider = summarize._repair_persian_draft(
        invalid,
        {
            "title": invalid["title"],
            "summary": source,
            "category": "ai",
            "link": "https://example.invalid/ai-evaluation",
        },
    )

    assert provider == "test-provider"
    assert "joined_verb_without_zwnj" in observed["prompt"]
    assert observed["providers"] is provider_sentinel
    assert "میتواند" not in candidate["summary"]
    assert summarize._language_ok(candidate)




def test_claim_alignment_semantic_failure_retries_with_independent_provider_family(monkeypatch):
    import src.summarize as summarize
    from src.llm_router_light import ProductionQualityChain

    first = {
        "title": "پژوهش درباره مدل هوش مصنوعی",
        "summary": "FIRST",
        "why_it_matters": "FIRST",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    repaired = {
        "title": "ارزیابی مستند یک مدل هوش مصنوعی",
        "summary": "READY",
        "why_it_matters": "READY",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    provider_chain = ProductionQualityChain([
        ("Groq:test-model", lambda *args, **kwargs: ""),
        ("OpenRouter:test-model", lambda *args, **kwargs: ""),
    ])
    responses = [
        (json.dumps(first, ensure_ascii=False), "Groq:test-model"),
        (json.dumps(repaired, ensure_ascii=False), "OpenRouter:test-model"),
    ]
    calls = []

    def fake_call(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(summarize, "get_quality_chain", lambda: provider_chain)
    monkeypatch.setattr(summarize, "call_llm_with_fallback", fake_call)
    monkeypatch.setattr(summarize, "_language_ok", lambda _candidate: True)
    monkeypatch.setattr(summarize, "_length_ok", lambda _candidate, _source: True)
    monkeypatch.setattr(summarize, "_value_ok", lambda _candidate, _source: True)

    def verified(candidate, _item, _source):
        flags = ["unsupported_comparison"] if candidate.get("summary") == "FIRST" else []
        candidate["_claim_verification"] = {"status": "VERIFIED", "flags": flags}
        return candidate

    monkeypatch.setattr(summarize, "_run_shadow_claim_verification", verified)
    candidate, provider = summarize._repair_claim_alignment(
        first,
        {"category": "ai", "title": "AI model evaluation"},
        "The source describes an AI model evaluation and its reported scope.",
        {"unsupported_comparison"},
    )

    assert len(calls) == 2
    assert isinstance(calls[0][1]["providers"], ProductionQualityChain)
    assert type(calls[1][1]["providers"]) is list
    assert [name for name, _ in calls[1][1]["providers"]] == ["OpenRouter:test-model"]
    assert candidate is not None
    assert candidate["summary"] == "READY"
    assert candidate["_claim_verification"]["flags"] == []
    assert provider == "OpenRouter:test-model"


def test_claim_alignment_recovery_can_use_opted_in_local_ollama_after_mistral(monkeypatch):
    import src.summarize as summarize
    from src.llm_router_light import ProductionQualityChain

    initial = {
        "title": "پژوهش درباره مدل هوش مصنوعی",
        "summary": "FIRST",
        "why_it_matters": "FIRST",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    repaired = {
        "title": "ارزیابی مستند یک مدل هوش مصنوعی",
        "summary": "READY",
        "why_it_matters": "READY",
        "speakers": "",
        "key_quote": "",
        "category": "ai",
    }
    provider_chain = ProductionQualityChain([
        ("Mistral:codestral-2508", lambda *_args, **_kwargs: ""),
    ])
    responses = [
        (json.dumps(initial, ensure_ascii=False), "Mistral:codestral-2508"),
        (json.dumps(repaired, ensure_ascii=False), "OllamaLocal:qwen3:1.7b:claim-repair"),
    ]
    calls = []
    monkeypatch.setenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "1")
    monkeypatch.setattr(summarize, "get_quality_chain", lambda: provider_chain)

    def fake_call(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(summarize, "call_llm_with_fallback", fake_call)
    monkeypatch.setattr(summarize, "_language_ok", lambda candidate: candidate.get("summary") == "READY")
    monkeypatch.setattr(summarize, "_length_ok", lambda candidate, _source: candidate.get("summary") == "READY")
    monkeypatch.setattr(summarize, "_value_ok", lambda candidate, _source: candidate.get("summary") == "READY")

    def verified(candidate, _item, _source):
        candidate["_claim_verification"] = {"status": "VERIFIED", "flags": []}
        return candidate

    monkeypatch.setattr(summarize, "_run_shadow_claim_verification", verified)
    candidate, provider = summarize._repair_claim_alignment(
        initial,
        {"category": "ai", "title": "AI model evaluation"},
        "The source describes an AI model evaluation and its reported scope.",
        {"unsupported_comparison"},
    )

    assert len(calls) == 2
    assert isinstance(calls[0][1]["providers"], ProductionQualityChain)
    assert [name for name, _ in calls[1][1]["providers"]] == [
        "OllamaLocal:qwen3:1.7b:claim-repair"
    ]
    assert candidate is not None
    assert candidate["summary"] == "READY"
    assert candidate["_claim_verification"]["flags"] == []
    assert provider == "OllamaLocal:qwen3:1.7b:claim-repair"


