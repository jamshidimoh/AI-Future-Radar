"""Run the isolated LiteLLM router pilot.

The script never prints API keys. It always executes a mocked fallback contract
test first, then performs one real smoke call when at least one credential is
available in the environment.
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
    print("[LiteLLM Pilot] mock_contract=PASS", flush=True)


def main() -> int:
    _mock_contract()

    from src.litellm_router_pilot import build_model_list, build_router, smoke_call

    rows = build_model_list()
    print(f"[LiteLLM Pilot] credentialed_deployments={len(rows)}", flush=True)
    for row in rows:
        print(
            f"[LiteLLM Pilot] deployment={row['model_info']['id']} "
            f"order={row['litellm_params']['order']}",
            flush=True,
        )

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
