import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from free_model_service import FreeModelIntelligence
import update_llm_health_state as persistence


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
