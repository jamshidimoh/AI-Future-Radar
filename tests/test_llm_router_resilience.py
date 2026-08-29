import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import llm_router_light as router


def _reset():
    router._DISABLED.clear()
    router._DISABLED_FAMILIES.clear()
    router._CHAIN_CACHE = None


def test_quota_failure_disables_provider_family(monkeypatch):
    _reset()
    calls = []

    def groq_fail(*args, **kwargs):
        calls.append("groq")
        raise router.QuotaExceeded("Groq qwen/qwen3.6-27b: HTTP 429")

    def gemini_ok(*args, **kwargs):
        calls.append("gemini")
        return '{"title":"ok"}'

    providers = [
        ("Groq:qwen/qwen3.6-27b", groq_fail),
        ("Groq:openai/gpt-oss-120b", groq_fail),
        ("Gemini", gemini_ok),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Gemini"
    assert calls == ["groq", "gemini"]


def test_auth_failure_does_not_try_sibling_openrouter_model():
    _reset()
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
        ("Groq:qwen/qwen3.6-27b", other_ok),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert calls == ["openrouter", "other"]


def test_current_default_chain_uses_supported_gemini_model(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    chain = router.get_quality_chain()
    names = [name for name, _ in chain]
    assert "Gemini" in names
    assert router.GEMINI_DEFAULT_MODEL == "gemini-3.7-flash"
    assert "OpenRouter:openai/gpt-oss-120b:free" in names
