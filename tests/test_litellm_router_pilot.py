from __future__ import annotations

import sys
import types


class _FakeResponse:
    def __init__(self):
        self.model = "groq/openai/gpt-oss-120b"
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content='{"ok":true}'))]


class _FakeRouter:
    last_kwargs = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeRouter.last_kwargs = kwargs

    def completion(self, **kwargs):
        self.call_kwargs = kwargs
        return _FakeResponse()


def _install_fake_litellm(monkeypatch):
    module = types.ModuleType("litellm")
    module.Router = _FakeRouter
    monkeypatch.setitem(sys.modules, "litellm", module)


def test_model_list_is_credential_driven(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("KIRAAI_API_KEY", "kira-test")
    monkeypatch.setattr("src.litellm_router_pilot.os.environ", {
        "OPENROUTER_API_KEY": "or-test",
        "GROQ_API_KEY": "groq-test",
        "KIRAAI_API_KEY": "kira-test",
    })

    from src.litellm_router_pilot import build_model_list

    rows = build_model_list()
    assert len(rows) == 5
    assert all(row["model_name"] == "radar-pilot" for row in rows)
    assert rows[0]["litellm_params"]["model"].startswith("openrouter/")
    assert rows[1]["litellm_params"]["model"].startswith("groq/")
    assert rows[-1]["litellm_params"]["api_base"] == "https://kiraai.vn/api/v1"


def test_router_config_uses_deployment_order_and_cooldown(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.delenv("KIRAAI_API_KEY", raising=False)
    _install_fake_litellm(monkeypatch)

    from src.litellm_router_pilot import build_router

    router = build_router()
    assert router.kwargs["num_retries"] == 0
    assert router.kwargs["allowed_fails"] == 1
    assert router.kwargs["cooldown_time"] == 45
    assert [
        row["litellm_params"]["order"] for row in router.kwargs["model_list"]
    ] == [1, 2, 3, 4]


def test_smoke_call_preserves_openai_style_response(monkeypatch):
    _install_fake_litellm(monkeypatch)

    from src.litellm_router_pilot import smoke_call

    content, selected = smoke_call(_FakeRouter())
    assert content == '{"ok":true}'
    assert selected == "groq/openai/gpt-oss-120b"
