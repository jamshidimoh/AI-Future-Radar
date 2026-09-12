import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import free_model_registry as registry
import llm_router_light as router
from production_router_policy import _is_provider_auth, _is_provider_quota


def test_nara_is_independent_fallback(monkeypatch):
    monkeypatch.setenv("NARAROUTER_API_KEY", "test-nara")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.delenv("KIRAAI_API_KEY", raising=False)
    names = [name for name, _ in registry.build_production_chain(router)]
    assert any(name.startswith("NaraRouter:") for name in names)


def test_nara_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("NARAROUTER_API_KEY", "test-nara")
    seen = {}

    class Response:
        status_code = 200
        text = '{"ok":true}'

        def json(self):
            return {"model": "auto/bynara", "choices": [{"message": {"content": '{"ok":true}'}}]}

        def raise_for_status(self):
            return None

    def post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(router.requests, "post", post)
    assert router._nara("system", "user", "auto/bynara") == '{"ok":true}'
    assert seen["url"] == "https://router.bynara.id/v1/chat/completions"


def test_json_generation_failure_does_not_disable_provider():
    message = "Failed to generate JSON. failed_generation=max completion tokens reached"
    assert not _is_provider_auth(message)
    assert not _is_provider_quota(message)
