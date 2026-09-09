"""Run the isolated LiteLLM router pilot.

The script never prints API keys. It validates LiteLLM fallback, probes each
credentialed provider independently, then runs the real multi-deployment
smoke call. Production Radar is not wired to this module yet.
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _mock_contract() -> None:
    class FakeResponse:
        model = "mock/fallback-model"
        choices = [types.SimpleNamespace(message=types.SimpleNamespace(content='{"ok":true}'))]

    class FakeRouter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def completion(self, **kwargs):
            assert kwargs["model"] == "radar-pilot"
            assert kwargs["response_format"] == {"type": "json_object"}
            return FakeResponse()

    import src.litellm_router_pilot as pilot
    content, selected = pilot.smoke_call(FakeRouter())
    assert json.loads(content)["ok"] is True
    assert selected == "mock/fallback-model"
    print("[LiteLLM Pilot] adapter_contract=PASS", flush=True)


def _litellm_fallback_contract() -> None:
    from litellm import Router

    router = Router(
        model_list=[
            {"model_name": "radar-fallback-primary", "litellm_params": {"model": "openai/fallback-primary", "mock_response": '{"route":"primary"}'}},
            {"model_name": "radar-fallback-secondary", "litellm_params": {"model": "openai/fallback-secondary", "mock_response": '{"route":"secondary"}'}},
        ],
        fallbacks=[{"radar-fallback-primary": ["radar-fallback-secondary"]}],
        num_retries=0,
        allowed_fails=1,
        cooldown_time=45,
    )
    response = router.completion(
        model="radar-fallback-primary",
        messages=[{"role": "user", "content": "fallback test"}],
        mock_testing_fallbacks=True,
    )
    content = response.choices[0].message.content or ""
    assert "secondary" in content
    print("[LiteLLM Pilot] router_fallback_contract=PASS", flush=True)


def _probe_provider(label: str, model: str, key_env: str, **kwargs) -> bool:
    key = os.getenv(key_env, "").strip()
    if not key:
        print(f"[LiteLLM Pilot] {label}_probe=SKIP reason=missing_credential", flush=True)
        return False
    import litellm
    try:
        response = litellm.completion(
            model=model,
            api_key=key,
            messages=[{"role": "user", "content": "Return exactly JSON: {\"ok\":true}"}],
            response_format={"type": "json_object"},
            max_tokens=32,
            timeout=8,
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        if not content:
            raise RuntimeError("empty response")
        print(f"[LiteLLM Pilot] {label}_probe=PASS", flush=True)
        return True
    except Exception as exc:
        print(f"[LiteLLM Pilot] {label}_probe=FAIL type={type(exc).__name__}: {exc}", flush=True)
        return False


def _probe_providers() -> None:
    _probe_provider("openrouter", "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "OPENROUTER_API_KEY")
    _probe_provider("groq", "groq/openai/gpt-oss-120b", "GROQ_API_KEY")
    _probe_provider("kiraai", "openai/minimax-m3-free", "KIRAAI_API_KEY", api_base="https://kiraai.vn/api/v1")
    _probe_provider("gemini", "gemini/gemini-3-flash-preview", "GEMINI_API_KEY")
    _probe_provider("cerebras", "cerebras/glm-4.7", "CEREBRAS_API_KEY")


def main() -> int:
    _mock_contract()
    _litellm_fallback_contract()
    _probe_providers()

    from src.litellm_router_pilot import build_model_list, build_router, smoke_call

    rows = build_model_list()
    print(f"[LiteLLM Pilot] credentialed_deployments={len(rows)}", flush=True)
    for row in rows:
        print(f"[LiteLLM Pilot] deployment={row['model_info']['id']} order={row['litellm_params']['order']}", flush=True)

    if not rows:
        print("[LiteLLM Pilot] real_smoke=SKIP reason=no_credentials", flush=True)
        return 0

    try:
        router = build_router()
        content, selected = smoke_call(router)
        if not content:
            raise RuntimeError("empty response")
        print(f"[LiteLLM Pilot] real_smoke=PASS selected={selected}", flush=True)
        print(f"[LiteLLM Pilot] response_preview={content[:160]!r}", flush=True)
        return 0
    except Exception as exc:
        print(f"[LiteLLM Pilot] real_smoke=FAIL type={type(exc).__name__}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
