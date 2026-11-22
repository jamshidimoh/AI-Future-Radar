"""Regression tests for live free-model catalog promotion."""

import yaml

import scripts.update_free_model_registry as updater
import src.free_model_registry as runtime


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _model(model_id, *, structured=True, free=True):
    return {
        "id": model_id,
        "pricing": {"prompt": "0" if free else "0.01", "completion": "0" if free else "0.02"},
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_parameters": ["structured_outputs"] if structured else [],
        "context_length": 32768,
        "top_provider": {"max_completion_tokens": 4096},
    }


def _registry(path):
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 5,
                    "require_free": True,
                    "require_chat": True,
                    "require_json_capability": True,
                    "max_runtime_candidates": 18,
                    "providers": [
                        {
                            "family": "openrouter",
                            "credential_env": "OPENROUTER_API_KEY",
                            "models": [],
                        }
                    ],
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_live_free_structured_catalog_models_enter_the_runtime_chain(tmp_path, monkeypatch):
    config_path = tmp_path / "free_model_registry.yaml"
    _registry(config_path)
    payload = {
        "data": [
            _model("deepseek/deepseek-v4-flash-0731:free"),
            _model("minimax/minimax-m3.1-flash:free"),
        ]
    }
    monkeypatch.setattr(updater, "REGISTRY", config_path)
    monkeypatch.setattr(updater.requests, "get", lambda *_args, **_kwargs: _Response(payload))
    monkeypatch.setattr(runtime, "REGISTRY_PATH", config_path)
    monkeypatch.setattr(runtime, "RUNTIME_REGISTRY_PATH", tmp_path / "runtime-registry.yaml")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")

    updater.refresh()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    rows = data["registry"]["providers"][0]["models"]
    assert len(rows) == 2
    for row in rows:
        assert row["free"] is True
        assert row["chat_capable"] is True
        assert row["json_capable"] is True
        assert row["priority"] < 1000
        assert row["base_quality"] > 0
        assert row["task_fit"] > 0
        assert row["quality_evidence"] == "openrouter-free-catalog-capability"

    entries = runtime.canonical_entries()
    promoted = {row["id"] for row in entries}
    assert promoted == {
        "deepseek/deepseek-v4-flash-0731:free",
        "minimax/minimax-m3.1-flash:free",
    }


def test_catalog_updater_keeps_nonfree_and_nonstructured_models_out(tmp_path, monkeypatch):
    config_path = tmp_path / "free_model_registry.yaml"
    _registry(config_path)
    payload = {
        "data": [
            _model("provider/paid-model:free", free=False),
            _model("provider/nonstructured-model:free", structured=False),
        ]
    }
    monkeypatch.setattr(updater, "REGISTRY", config_path)
    monkeypatch.setattr(updater.requests, "get", lambda *_args, **_kwargs: _Response(payload))

    updater.refresh()

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["registry"]["providers"][0]["models"] == []
