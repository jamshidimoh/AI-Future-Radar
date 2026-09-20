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
