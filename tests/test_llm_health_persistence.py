import json
from pathlib import Path

import scripts.update_llm_health_state as persistence
from src.free_model_service import FreeModelIntelligence

ROOT = Path(__file__).resolve().parents[1]


def _entry(model_id, family="openrouter", quality=90):
    return {
        "id": model_id,
        "deployment_id": f"{family}:{model_id}",
        "family": family,
        "free": True,
        "chat_capable": True,
        "json_capable": True,
        "quality_score": quality,
        "priority": 1,
    }


def test_model_failure_survives_new_intelligence_instance(tmp_path):
    state = tmp_path / "llm_health.json"
    first = FreeModelIntelligence(state, persist=True)
    first.mark_failure("openrouter:model-a", "HTTP 429", 3600)

    second = FreeModelIntelligence(state, persist=True)
    ranked = second.rank([_entry("model-a"), _entry("model-b", quality=80)])
    assert [row["id"] for row in ranked] == ["model-b"]


def test_provider_quota_skips_sibling_models_after_new_run(tmp_path):
    state = tmp_path / "llm_health.json"
    first = FreeModelIntelligence(state, persist=True)
    first.mark_failure("openrouter:model-a", "HTTP 402 account_limit", 3600, provider_family="openrouter", provider_scope=True)

    second = FreeModelIntelligence(state, persist=True)
    ranked = second.rank([_entry("model-a"), _entry("model-b", quality=80), _entry("other", family="groq", quality=70)])
    assert [row["id"] for row in ranked] == ["other"]


def test_log_persistence_distinguishes_plain_429_from_account_quota(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "[LiteLLM Router] failed=openrouter:model-a type=QuotaExceeded: HTTP 429 rate limit\n"
        "[LiteLLM Router] failed=openrouter:model-b type=QuotaExceeded: HTTP 402 account_limit\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "openrouter:model-a" in payload["models"]
    assert "openrouter:model-b" in payload["models"]
    assert "openrouter" in payload["providers"]


def test_provider_warning_failure_is_persisted(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "2026-09-13 WARNING src.llm_router_light: Provider quota attempt failed "
        "provider=groq model=qwen/qwen3.6-27b exception=QuotaExceeded: Groq qwen/qwen3.6-27b: HTTP 429 rate limit\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "groq:qwen/qwen3.6-27b" in payload["models"]
    assert payload["telemetry"]["observed_failures"] == 1


def test_provider_warning_failure_after_success_is_persisted(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "[Light Router] success=Groq:qwen/qwen3.6-27b\n"
        "2026-09-13 WARNING src.llm_router_light: Provider quota attempt failed "
        "provider=groq model=Groq:qwen/qwen3.6-27b exception=QuotaExceeded: HTTP 429 rate limit\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "groq:qwen/qwen3.6-27b" in payload["models"]
    assert payload["telemetry"]["observed_failures"] == 1


def test_success_after_failure_clears_latest_model_state(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "2026-09-13 WARNING src.llm_router_light: Provider quota attempt failed "
        "provider=groq model=Groq:qwen/qwen3.6-27b exception=QuotaExceeded: HTTP 429 rate limit\n"
        "[Light Router] success=Groq:qwen/qwen3.6-27b\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "groq:qwen/qwen3.6-27b" not in payload["models"]
    assert payload["telemetry"]["observed_failures"] == 1


def test_production_circuit_log_is_persisted(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "[Production Circuit] failed=openrouter:model-a reason=rate_limit scope=model: HTTP 429 upstream_provider_shared_pool\n"
        "[Production Circuit] success=groq:model-b model=groq/model-b attempts=2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "openrouter:model-a" in payload["models"]
    assert "groq:model-b" not in payload["models"]


def test_light_router_log_is_persisted(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "[Light Router] failed=groq:model-a reason=rate_limit scope=model: HTTP 429 rate limit\n"
        "[Light Router] success=groq:model-b model=groq/model-b attempts=1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "groq:model-a" in payload["models"]
    assert "groq:model-b" not in payload["models"]


def test_success_removes_persisted_model_failure(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    log = tmp_path / "run.log"
    log.write_text(
        "[LiteLLM Router] failed=groq:model-a type=QuotaExceeded: HTTP 429 rate limit\n"
        "[LiteLLM Router] success=groq:model-a model=model-a\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "groq:model-a" not in payload["models"]



def test_legacy_mixed_case_model_state_is_migrated_and_cleared_by_success(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    state.write_text(json.dumps({
        "models": {
            "Groq:qwen/qwen3.6-27b": {
                "failures": 2,
                "disabled_until": 0,
                "last_error": "rate_limit",
                "last_success": 0,
            }
        },
        "providers": {},
    }), encoding="utf-8")
    log = tmp_path / "run.log"
    log.write_text("[Light Router] success=groq:qwen/qwen3.6-27b model=groq/qwen3.6-27b\n", encoding="utf-8")
    monkeypatch.setattr(persistence, "STATE_PATH", state)
    monkeypatch.setattr(persistence.sys, "argv", ["update_llm_health_state.py", str(log)])
    assert persistence.main() == 0
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert "groq:qwen/qwen3.6-27b" not in payload["models"]
