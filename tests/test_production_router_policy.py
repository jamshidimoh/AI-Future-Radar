import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import llm_router_light as router
from production_router_policy import apply


def _reset(monkeypatch):
    router._DISABLED.clear()
    router._DISABLED_FAMILIES.clear()
    router._MODEL_DISABLED_UNTIL.clear()
    router._CHAIN_CACHE = None
    router._PRODUCTION_POLICY_APPLIED = False
    router._PRODUCTION_CIRCUIT_BREAKER_INSTALLED = False
    monkeypatch.delenv("RADAR_ENABLE_GEMINI_FALLBACK", raising=False)
    monkeypatch.delenv("RADAR_ENABLE_HF_FALLBACK", raising=False)
    monkeypatch.delenv("RADAR_MAX_LLM_ATTEMPTS", raising=False)
    monkeypatch.delenv("RADAR_ROUTER_BUDGET_SECONDS", raising=False)


def test_production_uses_canonical_router_module_and_trust_order(monkeypatch):
    _reset(monkeypatch)
    import summarize
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    apply()
    summarize_names = [name for name, _ in summarize.get_quality_chain()]
    router_names = [name for name, _ in router.get_quality_chain()]
    assert summarize_names == router_names
    assert router_names[0] == "OpenRouter:nvidia/nemotron-3-ultra-550b-a55b:free"
    assert router_names[1] == "OpenRouter:nvidia/nemotron-3-super-120b-a12b:free"
    assert router_names[2] == "Groq:openai/gpt-oss-120b"
    assert "Groq:qwen/qwen3.8-27b" not in router_names
    assert "OpenRouter:openai/gpt-oss-20b:free" in router_names
    assert router_names.index("OpenRouter:google/gemma-4-26b-a4b-it:free") < router_names.index("OpenRouter:openai/gpt-oss-20b:free")


def test_production_quota_is_model_scoped_and_sibling_can_failover(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
    calls = []
    def first_fails(*_args, **_kwargs):
        calls.append("gpt-oss")
        raise router.QuotaExceeded("Groq openai/gpt-oss-120b: HTTP 429")
    def sibling_ok(*_args, **_kwargs):
        calls.append("qwen")
        return '{"title":"ok"}'
    providers = [("Groq:openai/gpt-oss-120b", first_fails), ("Groq:qwen/qwen3.6-27b", sibling_ok)]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert calls == ["gpt-oss", "qwen"]
    assert "Groq:openai/gpt-oss-120b" in router._DISABLED
    assert "groq" not in router._DISABLED_FAMILIES


def test_production_model_permission_failure_is_model_scoped(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
    calls = []
    def blocked(*_args, **_kwargs):
        calls.append("blocked")
        raise router.QuotaExceeded("Groq qwen/qwen3.6-27b: HTTP 403 model_permission_blocked_project")
    def sibling_ok(*_args, **_kwargs):
        calls.append("sibling")
        return '{"title":"ok"}'
    providers = [("Groq:qwen/qwen3.6-27b", blocked), ("Groq:openai/gpt-oss-120b", sibling_ok)]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:openai/gpt-oss-120b"
    assert calls == ["blocked", "sibling"]
    assert "groq" not in router._DISABLED_FAMILIES
    assert "Groq:qwen/qwen3.6-27b" in router._DISABLED


def test_production_auth_failure_remains_family_scoped(monkeypatch):
    _reset(monkeypatch)
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
    providers = [("OpenRouter:openai/gpt-oss-120b:free", auth_fail), ("OpenRouter:openai/gpt-oss-20b:free", sibling), ("Groq:qwen/qwen3.6-27b", sibling)]
    result, provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert result == '{"title":"ok"}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert calls == ["openrouter", "sibling"]
    assert "openrouter" in router._DISABLED_FAMILIES


def test_quota_state_from_one_request_does_not_starve_sibling_in_next_request(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()
    calls = []
    def quota(*_args, **_kwargs):
        calls.append("quota")
        raise router.QuotaExceeded("Groq qwen/qwen3.6-27b: HTTP 429")
    def ok(*_args, **_kwargs):
        calls.append("ok")
        return '{"title":"ok"}'
    providers = [("Groq:qwen/qwen3.6-27b", quota), ("Groq:openai/gpt-oss-120b", ok)]
    first_result, first_provider = router.call_llm_with_fallback("system", "user", providers=providers)
    second_result, second_provider = router.call_llm_with_fallback("system", "user", providers=providers)
    assert first_result == '{"title":"ok"}'
    assert first_provider == "Groq:openai/gpt-oss-120b"
    assert second_result == '{"title":"ok"}'
    assert second_provider == "Groq:openai/gpt-oss-120b"
    assert calls == ["quota", "ok", "ok"]


def test_production_provider_quota_skips_all_siblings_and_switches_provider(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("RADAR_MAX_LLM_ATTEMPTS", "4")
    apply()
    calls = []

    class FakeRouter:
        def completion(self, *, model, **_kwargs):
            calls.append(model)
            if model in {"radar-production-1", "radar-production-2"}:
                raise RuntimeError("HTTP 429 account_limit; daily quota exhausted")
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{\"title\":\"ok\"}'})()})()]},
            )()

    deployments = [
        {"model_name": "radar-production-1", "model_info": {"id": "openrouter:model-a"}},
        {"model_name": "radar-production-2", "model_info": {"id": "openrouter:model-b"}},
        {"model_name": "radar-production-3", "model_info": {"id": "groq:model-c"}},
    ]
    monkeypatch.setattr(router, "_get_litellm_router", lambda: FakeRouter())
    monkeypatch.setattr(router, "_litellm_model_list", lambda: deployments)
    result, provider = router._call_litellm("system", "user")
    assert result == '{"title":"ok"}'
    assert provider == "groq:model-c"
    assert calls == ["radar-production-1", "radar-production-3"]
    assert "openrouter" in router._DISABLED_FAMILIES


def test_production_model_429_does_not_disable_provider(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    apply()

    class FakeRouter:
        def completion(self, *, model, **_kwargs):
            calls.append(model)
            if model == "radar-production-1":
                raise RuntimeError("HTTP 429 model rate limit")
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{\"title\":\"ok\"}'})()})()]},
            )()

    calls = []
    deployments = [
        {"model_name": "radar-production-1", "model_info": {"id": "groq:model-a"}},
        {"model_name": "radar-production-2", "model_info": {"id": "groq:model-b"}},
    ]
    monkeypatch.setattr(router, "_get_litellm_router", lambda: FakeRouter())
    monkeypatch.setattr(router, "_litellm_model_list", lambda: deployments)
    result, provider = router._call_litellm("system", "user")
    assert result == '{"title":"ok"}'
    assert provider == "groq:model-b"
    assert calls == ["radar-production-1", "radar-production-2"]
    assert "groq" not in router._DISABLED_FAMILIES


def test_production_openrouter_upstream_shared_pool_is_model_scoped(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("RADAR_MAX_LLM_ATTEMPTS", "4")
    apply()
    calls = []

    class FakeRouter:
        def completion(self, *, model, **_kwargs):
            calls.append(model)
            if model == "radar-production-1":
                raise RuntimeError("HTTP 429 upstream_provider_shared_pool")
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{\"title\":\"ok\"}'})()})()]},
            )()

    deployments = [
        {"model_name": "radar-production-1", "model_info": {"id": "openrouter:model-a"}},
        {"model_name": "radar-production-2", "model_info": {"id": "openrouter:model-b"}},
        {"model_name": "radar-production-3", "model_info": {"id": "groq:model-c"}},
    ]
    monkeypatch.setattr(router, "_get_litellm_router", lambda: FakeRouter())
    monkeypatch.setattr(router, "_litellm_model_list", lambda: deployments)
    result, provider = router._call_litellm("system", "user")
    assert result == '{"title":"ok"}'
    assert provider == "openrouter:model-b"
    assert calls == ["radar-production-1", "radar-production-2"]
    assert "openrouter" not in router._DISABLED_FAMILIES
    assert "openrouter:model-a" in router._DISABLED


def test_kira_wallet_error_does_not_disable_kira_family(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("KIRAAI_API_KEY", "test-kira")
    apply()
    calls = []

    class FakeRouter:
        def completion(self, *, model, **_kwargs):
            calls.append(model)
            if model == "radar-production-1":
                raise RuntimeError("Insufficient VND wallet balance (0 VND remaining)")
            return type(
                "Response",
                (),
                {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{\"title\":\"ok\"}'})()})()]},
            )()

    deployments = [
        {"model_name": "radar-production-1", "model_info": {"id": "kiraai:model-a"}},
        {"model_name": "radar-production-2", "model_info": {"id": "kiraai:model-b"}},
    ]
    monkeypatch.setattr(router, "_get_litellm_router", lambda: FakeRouter())
    monkeypatch.setattr(router, "_litellm_model_list", lambda: deployments)
    result, provider = router._call_litellm("system", "user")
    assert result == '{"title":"ok"}'
    assert provider == "kiraai:model-b"
    assert calls == ["radar-production-1", "radar-production-2"]
    assert "kiraai" not in router._DISABLED_FAMILIES


def test_huggingface_is_last_resort_emergency_lane(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("KIRAAI_API_KEY", "test-kira")
    monkeypatch.setenv("HF_TOKEN", "test-hf")
    monkeypatch.setenv("RADAR_ENABLE_HF_FALLBACK", "1")
    monkeypatch.setenv("RADAR_MAX_LLM_ATTEMPTS", "1")
    apply()

    class FakeRouter:
        def completion(self, **_kwargs):
            raise RuntimeError("HTTP 503 temporary")

    monkeypatch.setattr(router, "_get_litellm_router", lambda: FakeRouter())
    monkeypatch.setattr(router, "_litellm_model_list", lambda: [{"model_name": "radar-production-1", "model_info": {"id": "kiraai:model-a"}}])
    monkeypatch.setattr(router, "_huggingface", lambda *_args, **_kwargs: '{"title":"hf"}')

    result, provider = router._call_litellm("system", "user")
    assert result == '{"title":"hf"}'
    assert provider == "HuggingFace"


def test_production_attempt_budget_is_hard_capped(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("RADAR_MAX_LLM_ATTEMPTS", "2")
    apply()

    class FakeRouter:
        def completion(self, **_kwargs):
            calls.append(1)
            raise RuntimeError("HTTP 503 temporary")

    calls = []
    deployments = [
        {"model_name": f"radar-production-{i}", "model_info": {"id": f"groq:model-{i}"}}
        for i in range(1, 6)
    ]
    monkeypatch.setattr(router, "_get_litellm_router", lambda: FakeRouter())
    monkeypatch.setattr(router, "_litellm_model_list", lambda: deployments)
    result, provider = router._call_litellm("system", "user")
    assert result is None
    assert provider is None
    assert len(calls) == 2


def test_production_launcher_does_not_activate_router_on_import(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.delenv("RADAR_PRODUCTION_MODE", raising=False)
    sys.modules.pop("scripts.production_with_ranking_audit", None)
    import scripts.production_with_ranking_audit
    assert router._PRODUCTION_POLICY_APPLIED is False


def test_production_launcher_activates_router_when_production_mode_is_enabled(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("RADAR_PRODUCTION_MODE", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    sys.modules.pop("scripts.production_with_ranking_audit", None)
    import scripts.production_with_ranking_audit
    assert router._PRODUCTION_POLICY_APPLIED is True
