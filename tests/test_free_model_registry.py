import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import free_model_registry as registry
import llm_router_light as router


def _reset(monkeypatch):
    router._DISABLED.clear()
    router._DISABLED_FAMILIES.clear()
    router._MODEL_DISABLED_UNTIL.clear()
    router._CHAIN_CACHE = None
    router._PRODUCTION_POLICY_APPLIED = True
    monkeypatch.delenv("RADAR_ENABLE_GEMINI_FALLBACK", raising=False)
    monkeypatch.delenv("RADAR_ENABLE_HF_FALLBACK", raising=False)


def test_canonical_trust_order_is_explicit_not_score_sorted(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    names = [name for name, _ in registry.build_production_chain(router)]
    assert names == [
        "OpenRouter:nvidia/nemotron-3-ultra-550b-a55b:free",
        "OpenRouter:nvidia/nemotron-3-super-120b-a12b:free",
        "Groq:openai/gpt-oss-120b",
        "Groq:qwen/qwen3.6-27b",
        "OpenRouter:openai/gpt-oss-120b:free",
        "OpenRouter:google/gemma-4-31b-it:free",
        "OpenRouter:qwen/qwen3-next-80b-a3b-instruct:free",
        "OpenRouter:google/gemma-4-26b-a4b-it:free",
        "OpenRouter:nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "Groq:openai/gpt-oss-20b",
        "OpenRouter:openai/gpt-oss-20b:free",
    ]


def test_retired_nemotron_nano_and_qwen38_are_not_trusted(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    rows = registry.canonical_entries()
    ids = {row["id"] for row in rows}
    assert "qwen/qwen3.8-27b" not in ids
    assert "nvidia/nemotron-3-nano-30b-a3b:free" not in ids
    assert "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free" in ids


def test_nemotron_ultra_uses_prompt_json_not_response_format(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    assert registry.model_capability("nvidia/nemotron-3-ultra-550b-a55b:free")["json_capable"] is True
    assert registry.model_capability("nvidia/nemotron-3-ultra-550b-a55b:free")["response_format"] is False

    seen = {}

    class Response:
        status_code = 200
        text = ''

        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

        def raise_for_status(self):
            return None

    def post(_url, **kwargs):
        seen.update(kwargs.get("json", {}))
        return Response()

    monkeypatch.setattr(router.requests, "post", post)
    result = router._openrouter("system", "user", "nvidia/nemotron-3-ultra-550b-a55b:free")
    assert result == '{"ok":true}'
    assert "response_format" not in seen


def test_quota_is_model_scoped_and_openrouter_daily_limit_is_family_scoped(monkeypatch):
    _reset(monkeypatch)
    calls = []

    def groq_quota(*_args, **_kwargs):
        calls.append("groq-quota")
        raise router.QuotaExceeded("Groq openai/gpt-oss-120b: HTTP 429")

    def groq_ok(*_args, **_kwargs):
        calls.append("groq-ok")
        return '{"ok":true}'

    result, provider = router.call_llm_with_fallback(
        "s",
        "u",
        providers=[
            ("Groq:openai/gpt-oss-120b", groq_quota),
            ("Groq:qwen/qwen3.6-27b", groq_ok),
        ],
    )
    assert result == '{"ok":true}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert "groq" not in router._DISABLED_FAMILIES

    _reset(monkeypatch)
    def or_daily(*_args, **_kwargs):
        calls.append("or-daily")
        raise router.QuotaExceeded("OpenRouter model: HTTP 429 free tier requests/day exceeded")

    def or_sibling(*_args, **_kwargs):
        calls.append("or-sibling")
        return '{"ok":true}'

    result, provider = router.call_llm_with_fallback(
        "s",
        "u",
        providers=[
            ("OpenRouter:a:free", or_daily),
            ("OpenRouter:b:free", or_sibling),
            ("Groq:qwen/qwen3.6-27b", groq_ok),
        ],
    )
    assert result == '{"ok":true}'
    assert provider == "Groq:qwen/qwen3.6-27b"
    assert "openrouter" in router._DISABLED_FAMILIES


def test_optional_gemini_and_hf_are_disabled_by_default(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    names = [name for name, _ in registry.build_production_chain(router)]
    assert "Gemini" not in names
    assert "HuggingFace" not in names

    monkeypatch.setenv("RADAR_ENABLE_GEMINI_FALLBACK", "1")
    names = [name for name, _ in registry.build_production_chain(router)]
    assert names[-1] == "Gemini"
