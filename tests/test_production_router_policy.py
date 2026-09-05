import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import llm_router_light as router
from production_router_policy import apply


def _reset():
    router._DISABLED.clear()
    router._DISABLED_FAMILIES.clear()
    router._CHAIN_CACHE = None
    router._PRODUCTION_POLICY_APPLIED = False


def test_production_quota_is_model_scoped_and_sibling_can_failover(monkeypatch):
    _reset()
    apply()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def first_fails(*_args, **_kwargs):
        calls.append("qwen")
        raise router.QuotaExceeded("Groq qwen/qwen3.8-27b: HTTP 429")

    def sibling_ok(*_args, **_kwargs):
        calls.append("gpt-oss")
        return '{"title":"ok"}'

    providers = [
        ("Groq:qwen/qwen3.8-27b", first_fails),
        ("Groq:openai/gpt-oss-120b", sibling_ok),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:openai/gpt-oss-120b"
    assert calls == ["qwen", "gpt-oss"]
    assert "Groq:qwen/qwen3.8-27b" in router._DISABLED
    assert "groq" not in router._DISABLED_FAMILIES


def test_production_auth_failure_remains_family_scoped(monkeypatch):
    _reset()
    apply()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def auth_fail(*_args, **_kwargs):
        calls.append("openrouter")
        raise router.QuotaExceeded("OpenRouter openai/gpt-oss-120b:free: HTTP 401")

    def sibling(*_args, **_kwargs):
        calls.append("sibling")
        return '{"title":"ok"}'

    providers = [
        ("OpenRouter:openai/gpt-oss-120b:free", auth_fail),
        ("OpenRouter:openai/gpt-oss-20b:free", sibling),
        ("Groq:qwen/qwen3.8-27b", sibling),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.8-27b"
    assert calls == ["openrouter", "sibling"]
    assert "openrouter" in router._DISABLED_FAMILIES


def test_quota_state_from_one_request_does_not_starve_sibling_in_next_request(monkeypatch):
    _reset()
    apply()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def quota(*_args, **_kwargs):
        calls.append("quota")
        raise router.QuotaExceeded("Groq qwen/qwen3.8-27b: HTTP 429")

    def ok(*_args, **_kwargs):
        calls.append("ok")
        return '{"title":"ok"}'

    providers = [
        ("Groq:qwen/qwen3.8-27b", quota),
        ("Groq:openai/gpt-oss-120b", ok),
    ]

    first_result, first_provider = router.call_llm_with_fallback("system", "user", providers=providers)
    second_result, second_provider = router.call_llm_with_fallback("system", "user", providers=providers)

    assert first_result == '{"title":"ok"}'
    assert first_provider == "Groq:openai/gpt-oss-120b"
    assert second_result == '{"title":"ok"}'
    assert second_provider == "Groq:openai/gpt-oss-120b"
    assert calls == ["quota", "ok", "quota", "ok"]
