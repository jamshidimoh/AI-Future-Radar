import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import llm_router_light as router
from production_router_policy import apply


def _reset():
    router._DISABLED.clear()
    router._DISABLED_FAMILIES.clear()
    router._MODEL_DISABLED_UNTIL.clear()
    router._CHAIN_CACHE = None
    router._PRODUCTION_POLICY_APPLIED = False


def test_production_uses_canonical_router_module(monkeypatch):
    _reset()
    import summarize

    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    apply()
    assert summarize.get_quality_chain() == router.get_quality_chain()
    names = [name for name, _ in router.get_quality_chain()]
    assert names[0] == "Groq:qwen/qwen3.8-27b"
    assert any(name.startswith("Groq:") for name in names)
    assert any(name.startswith("OpenRouter:") for name in names)
    assert names[-1] == "Gemini"


def test_production_quota_is_model_scoped_and_sibling_can_failover(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
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


def test_production_model_permission_failure_is_model_scoped(monkeypatch):
    _reset()
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
    calls = []

    def blocked(*_args, **_kwargs):
        calls.append("blocked")
        raise router.QuotaExceeded("Groq qwen/qwen3.8-27b: HTTP 403 model_permission_blocked_project")

    def sibling_ok(*_args, **_kwargs):
        calls.append("sibling")
        return '{"title":"ok"}'

    providers = [
        ("Groq:qwen/qwen3.8-27b", blocked),
        ("Groq:openai/gpt-oss-120b", sibling_ok),
    ]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:openai/gpt-oss-120b"
    assert calls == ["blocked", "sibling"]
    assert "groq" not in router._DISABLED_FAMILIES
    assert "Groq:qwen/qwen3.8-27b" in router._DISABLED


def test_production_auth_failure_remains_family_scoped(monkeypatch):
    _reset()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
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
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
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
    assert calls == ["quota", "ok", "ok"]


def test_production_launcher_does_not_activate_router_on_import(monkeypatch):
    _reset()
    monkeypatch.delenv("RADAR_PRODUCTION_MODE", raising=False)
    sys.modules.pop("scripts.production_with_ranking_audit", None)
    import scripts.production_with_ranking_audit  # noqa: F401
    assert router._PRODUCTION_POLICY_APPLIED is False


def test_production_launcher_activates_router_when_production_mode_is_enabled(monkeypatch):
    _reset()
    monkeypatch.setenv("RADAR_PRODUCTION_MODE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    sys.modules.pop("scripts.production_with_ranking_audit", None)
    import scripts.production_with_ranking_audit  # noqa: F401
    assert router._PRODUCTION_POLICY_APPLIED is True
