from __future__ import annotations

import copy

import scripts.bridge_free_llm_router as bridge
import scripts.refresh_free_model_registry as refresh


def _model(model_id="vendor/free-chat"):
    return {
        "id": model_id,
        "priority": 1,
        "base_quality": 70,
        "task_fit": 70,
        "quality_evidence": "curated-independent",
    }


def _live_model(*, json_capable=True, text_io=True):
    modalities = ["text"] if text_io else ["image"]
    parameters = ["response_format"] if json_capable else []
    return {
        "id": "vendor/free-chat",
        "pricing": {"prompt": "0", "completion": "0"},
        "context_length": 32768,
        "architecture": {"input_modalities": modalities, "output_modalities": modalities},
        "supported_parameters": parameters,
    }


def test_refresh_populates_live_chat_and_json_capabilities_for_legacy_trusted_rows(monkeypatch, tmp_path):
    runtime_path = tmp_path / "registry.runtime.yaml"
    monkeypatch.setattr(refresh, "RUNTIME_PATH", runtime_path)
    monkeypatch.setattr(
        refresh,
        "_load_static",
        lambda: {
            "registry": {
                "require_free": True,
                "require_chat": True,
                "require_json_capability": True,
                "stale_after_hours": 72,
                "providers": [
                    {
                        "family": "openrouter",
                        "credential_env": "OPENROUTER_API_KEY",
                        "models": [_model()],
                    }
                ],
            }
        },
    )
    live = _live_model()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("KIRAAI_API_KEY", "test-kira")
    monkeypatch.setenv("FREE_LLM_ROUTER_API_KEY", "test-router")
    monkeypatch.setattr(refresh, "_openrouter_auth", lambda _token: (True, "credential valid"))
    monkeypatch.setattr(refresh, "_openrouter_models", lambda _token: ({"vendor/free-chat": live}, "catalog ok"))
    monkeypatch.setattr(refresh, "_openrouter_benchmarks", lambda _token: ({}, "benchmark catalog ok"))
    monkeypatch.setattr(refresh, "_openrouter_task_evidence", lambda _token: {})
    monkeypatch.setattr(refresh, "_groq_models", lambda _token: (True, {}, "catalog ok"))
    monkeypatch.setattr(refresh, "_kira_models", lambda _token: (True, {}, "catalog ok"))
    monkeypatch.setattr(refresh, "_free_llm_router_ids", lambda _token: (True, [], "catalog ok"))

    runtime = refresh.refresh()
    model = runtime["registry"]["providers"][0]["models"][0]

    assert model["enabled"] is True
    assert model["free"] is True
    assert model["chat_capable"] is True
    assert model["json_capable"] is True
    assert model["response_format"] is True
    assert runtime_path.exists()


def test_refresh_does_not_mark_media_only_openrouter_models_as_chat_capable(monkeypatch, tmp_path):
    model = _model()
    refresh._apply_live_capabilities(model, _live_model(json_capable=True, text_io=False))

    assert model["chat_capable"] is False
    # A trusted JSON prior does not turn a media-only endpoint into a chat model.


def test_dynamic_bridge_requires_explicit_json_capability_for_untrusted_models():
    assert bridge._json_chat_capable(_live_model(json_capable=True)) is True
    assert bridge._json_chat_capable(_live_model(json_capable=False)) is False
    assert bridge._json_chat_capable(_live_model(json_capable=True, text_io=False)) is False


def test_dynamic_bridge_reports_unusable_json_candidates_as_rejected(monkeypatch, tmp_path):
    runtime_path = tmp_path / "registry.runtime.yaml"
    source = {
        "runtime": {"generated_at": "2026-10-19T00:00:00+00:00", "discovery_candidates": []},
        "registry": {"providers": []},
    }
    flr_model = {"id": "vendor/free-chat"}
    live = _live_model(json_capable=False)
    monkeypatch.setattr(bridge, "RUNTIME_PATH", runtime_path)
    monkeypatch.setattr(bridge, "_load", lambda: copy.deepcopy(source))
    monkeypatch.setenv("FREE_LLM_ROUTER_API_KEY", "test-router")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    def fake_get_json(url, *, token=None, query=None):
        if url.endswith("/models/full"):
            return 200, {"models": [flr_model], "feedbackCounts": {}, "lastUpdated": "2026-10-19"}
        if url.endswith("/models"):
            return 200, {"data": [live]}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(bridge, "_get_json", fake_get_json)

    result = bridge.bridge()

    status = result["runtime"]["flr_bridge"]
    assert status["accepted_models"] == 0
    assert status["rejected_models"] == 1
    assert status["rejection_reasons"] == {"no_json_capability": 1}
    assert result["runtime"]["discovery_candidates"] == []
