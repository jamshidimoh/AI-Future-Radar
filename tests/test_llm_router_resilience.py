from pathlib import Path

import src.llm_router_light as router

ROOT = Path(__file__).resolve().parents[1]


def _reset():
    router._DISABLED.clear()
    router._DISABLED_FAMILIES.clear()
    router._MODEL_DISABLED_UNTIL.clear()
    router._MODEL_DISABLED_REASON.clear()
    router._CHAIN_CACHE = None
    router._PRODUCTION_POLICY_APPLIED = False
    router._OLLAMA_CIRCUIT_OPEN = False
    router._PRODUCTION_CIRCUIT_OPEN = False


def test_model_specific_quota_keeps_provider_sibling_available(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def groq_qwen_quota(*args, **kwargs):
        calls.append("qwen")
        raise router.QuotaExceeded("Groq qwen/qwen3.8-27b: HTTP 429")

    def groq_sibling_ok(*args, **kwargs):
        calls.append("gpt-oss")
        return '{"title":"ok"}'

    providers = [
        ("Groq:qwen/qwen3.8-27b", groq_qwen_quota),
        ("Groq:openai/gpt-oss-120b", groq_sibling_ok),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:openai/gpt-oss-120b"
    assert calls == ["qwen", "gpt-oss"]
    assert "groq" not in router._DISABLED_FAMILIES


def test_auth_failure_does_not_try_sibling_openrouter_model(monkeypatch):
    _reset()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def openrouter_fail(*args, **kwargs):
        calls.append("openrouter")
        raise router.QuotaExceeded("OpenRouter openai/gpt-oss-120b:free: HTTP 401")

    def other_ok(*args, **kwargs):
        calls.append("other")
        return '{"title":"ok"}'

    providers = [
        ("OpenRouter:openai/gpt-oss-120b:free", openrouter_fail),
        ("OpenRouter:openai/gpt-oss-20b:free", openrouter_fail),
        ("Groq:qwen/qwen3.8-27b", other_ok),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.8-27b"
    assert calls == ["openrouter", "other"]
    assert "openrouter" in router._DISABLED_FAMILIES


def test_current_default_chain_uses_current_supported_policy(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.delenv("RADAR_ENABLE_GEMINI_FALLBACK", raising=False)
    chain = router.get_quality_chain()
    names = [name for name, _ in chain]
    assert "Gemini" not in names
    assert router.GEMINI_DEFAULT_MODEL == "gemini-3.8-flash"
    assert "Groq:qwen/qwen3.6-27b" in names
    assert "OpenRouter:openai/gpt-oss-120b:free" in names


def test_model_permission_failure_is_not_family_scoped(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "x")
    calls = []

    def blocked(*args, **kwargs):
        calls.append("blocked")
        raise router.QuotaExceeded("Groq openai/gpt-oss-120b: HTTP 403 model_permission_blocked_project")

    def sibling(*args, **kwargs):
        calls.append("sibling")
        return '{"title":"ok"}'

    result, provider = router.call_llm_with_fallback(
        "system",
        "user",
        providers=[
            ("Groq:openai/gpt-oss-120b", blocked),
            ("Groq:qwen/qwen3.6-27b", sibling),
        ],
    )
    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert calls == ["blocked", "sibling"]
    assert "groq" not in router._DISABLED_FAMILIES


def test_recovery_reset_clears_only_retryable_model_cooldowns(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    router._disable("Groq:model-quota", "quota")
    router._disable("Groq:model-transient", "transient")
    router._disable("Groq:model-model", "model")
    router._DISABLED_FAMILIES.add("openrouter")
    cleared = router.reset_recoverable_cooldowns()
    assert cleared == 2
    assert "Groq:model-quota" not in router._DISABLED
    assert "Groq:model-transient" not in router._DISABLED
    assert "Groq:model-model" in router._DISABLED
    assert "openrouter" in router._DISABLED_FAMILIES




def test_wallet_exhaustion_is_family_scoped_and_survives_recovery_reset():
    _reset()
    message = (
        "KiraAI model: HTTP 402 Insufficient VND wallet balance "
        "(0 VND remaining), code=vnd_balance_exhausted"
    )
    assert router._failure_class(message) == "billing"
    assert router._provider_quota_is_family_scoped("kiraai", "billing", message)

    router._disable("KiraAI:model-wallet-empty", "billing")
    router._DISABLED_FAMILIES.add("kiraai")
    cleared = router.reset_recoverable_cooldowns()

    assert cleared == 0
    assert "KiraAI:model-wallet-empty" in router._DISABLED
    assert router._MODEL_DISABLED_REASON["KiraAI:model-wallet-empty"] == "billing"
    assert "kiraai" in router._DISABLED_FAMILIES


def test_wallet_exhaustion_skips_sibling_models_but_keeps_other_provider_fallback(monkeypatch):
    _reset()
    monkeypatch.setenv("KIRAAI_API_KEY", "test-kiraai")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def wallet_empty(*args, **kwargs):
        calls.append("kiraai-first")
        raise router.QuotaExceeded(
            "KiraAI model: HTTP 402 Insufficient VND wallet balance (0 VND remaining); "
            "code=vnd_balance_exhausted"
        )

    def kiraai_sibling(*args, **kwargs):
        calls.append("kiraai-sibling")
        return '{"title":"should not be used"}'

    def groq_fallback(*args, **kwargs):
        calls.append("groq-fallback")
        return '{"title":"ok"}'

    result, provider = router.call_llm_with_fallback(
        "system",
        "user",
        providers=[
            ("KiraAI:model-a", wallet_empty),
            ("KiraAI:model-b", kiraai_sibling),
            ("Groq:qwen/qwen3.6-27b", groq_fallback),
        ],
    )

    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert calls == ["kiraai-first", "groq-fallback"]
    assert "kiraai" in router._DISABLED_FAMILIES



def test_no_zero_price_huggingface_is_family_scoped_and_survives_recovery_reset():
    _reset()
    message = "No zero-price Hugging Face chat model is currently available"
    assert router._failure_class(message) == "unavailable"
    assert router._provider_quota_is_family_scoped("huggingface", "unavailable", message)

    router._disable("HuggingFace", "unavailable")
    router._DISABLED_FAMILIES.add("huggingface")
    assert router.reset_recoverable_cooldowns() == 0
    assert "HuggingFace" in router._DISABLED
    assert "huggingface" in router._DISABLED_FAMILIES


def test_unavailable_huggingface_skips_provider_retries_but_keeps_other_fallback(monkeypatch):
    _reset()
    monkeypatch.setenv("HF_TOKEN", "test-hf")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def hf_unavailable(*args, **kwargs):
        calls.append("hf-first")
        raise router.QuotaExceeded("No zero-price Hugging Face chat model is currently available")

    def hf_sibling(*args, **kwargs):
        calls.append("hf-sibling")
        return '{"title":"should not be used"}'

    def groq_fallback(*args, **kwargs):
        calls.append("groq-fallback")
        return '{"title":"ok"}'

    result, provider = router.call_llm_with_fallback(
        "system",
        "user",
        providers=[
            ("HuggingFace:model-a", hf_unavailable),
            ("HuggingFace:model-b", hf_sibling),
            ("Groq:openai/gpt-oss-20b", groq_fallback),
        ],
    )

    assert result == '{"title":"ok"}'
    assert provider == "Groq:openai/gpt-oss-20b"
    assert calls == ["hf-first", "groq-fallback"]
    assert "huggingface" in router._DISABLED_FAMILIES


def test_nar_router_telegram_link_requirement_is_family_scoped_auth():
    _reset()
    message = (
        'NaraRouter auto/bynara: HTTP 403 {"error":{"type":"forbidden",'
        '"message":"telegram_required: Join the required Telegram group/channel '
        'and relink at /settings to continue."}}'
    )
    assert router._failure_class(message) == "auth"
    assert router._provider_quota_is_family_scoped("nararouter", "auth", message)

    router._disable("NaraRouter:auto/bynara", "auth")
    router._DISABLED_FAMILIES.add("nararouter")
    assert router.reset_recoverable_cooldowns() == 0
    assert "nararouter" in router._DISABLED_FAMILIES


def test_nara_router_telegram_link_requirement_skips_siblings_but_keeps_other_fallback(monkeypatch):
    _reset()
    monkeypatch.setenv("NARAROUTER_API_KEY", "test-nara")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def nara_requires_link(*args, **kwargs):
        calls.append("nara-first")
        raise router.QuotaExceeded(
            "NaraRouter auto/bynara: HTTP 403 telegram_required: Join the required Telegram group/channel and relink at /settings to continue"
        )

    def nara_sibling(*args, **kwargs):
        calls.append("nara-sibling")
        return '{"title":"should not be used"}'

    def groq_fallback(*args, **kwargs):
        calls.append("groq-fallback")
        return '{"title":"ok"}'

    result, provider = router.call_llm_with_fallback(
        "system",
        "user",
        providers=[
            ("NaraRouter:auto/bynara", nara_requires_link),
            ("NaraRouter:model-b", nara_sibling),
            ("Groq:openai/gpt-oss-20b", groq_fallback),
        ],
    )

    assert result == '{"title":"ok"}'
    assert provider == "Groq:openai/gpt-oss-20b"
    assert calls == ["nara-first", "groq-fallback"]
    assert "nararouter" in router._DISABLED_FAMILIES


def test_groq_gpt_oss_retries_without_json_mode_on_validation_failure(monkeypatch):
    calls = []

    class FakeLiteLLMRouter:
        def completion(self, **kwargs):
            calls.append(dict(kwargs))
            if "response_format" in kwargs:
                raise RuntimeError("GroqException: json_validate_failed")
            return type("Response", (), {
                "choices": [type("Choice", (), {
                    "message": type("Message", (), {"content": "{\\\"title\\\":\\\"ok\\\"}"})()
                })()],
                "model": "groq/openai/gpt-oss-120b",
            })()

    deployment = {
        "model_name": "radar-production-1",
        "model_info": {
            "id": "groq:openai/gpt-oss-120b",
            "response_format": True,
        },
    }
    response = router._call_direct_deployment(
        FakeLiteLLMRouter(), deployment, "system", "user", max_tokens=1100, timeout=4
    )
    assert response.choices[0].message.content == "{\\\"title\\\":\\\"ok\\\"}"
    assert len(calls) == 2
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in calls[1]



def test_local_ollama_recovery_provider_is_credential_free_but_opt_in(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "1")
    assert router._provider_credential_available("OllamaLocal:qwen3:1.7b:mission-persian-repair")
    assert router._provider_credential_available("ollama:qwen3:1.7b")

    router._OLLAMA_CIRCUIT_OPEN = True
    assert not router._provider_credential_available("OllamaLocal:qwen3:1.7b:mission-persian-repair")
    router._OLLAMA_CIRCUIT_OPEN = False

    monkeypatch.setenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "0")
    assert not router._provider_credential_available("OllamaLocal:qwen3:1.7b:mission-persian-repair")


def test_mission_recovery_chain_can_select_local_ollama_without_api_key(monkeypatch):
    _reset()
    monkeypatch.setenv("RADAR_ENABLE_LOCAL_OLLAMA_FALLBACK", "1")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    calls = []

    def ollama_repair(*args, **kwargs):
        calls.append("ollama")
        return '{"title":"ترمیم فارسی"}'

    result, provider = router.call_llm_with_fallback(
        "system",
        "user",
        providers=[("OllamaLocal:qwen3:1.7b:mission-persian-repair", ollama_repair)],
    )

    assert result == '{"title":"ترمیم فارسی"}'
    assert provider == "OllamaLocal:qwen3:1.7b:mission-persian-repair"
    assert calls == ["ollama"]
