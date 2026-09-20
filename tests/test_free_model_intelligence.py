from pathlib import Path

from src.free_model_service import FreeModelIntelligence

ROOT = Path(__file__).resolve().parents[1]


def _entry(model_id, quality, priority=1):
    return {
        "id": model_id,
        "deployment_id": model_id,
        "free": True,
        "chat_capable": True,
        "json_capable": True,
        "quality_score": quality,
        "priority": priority,
    }


def test_quality_is_primary_after_availability_gate():
    intelligence = FreeModelIntelligence()
    high = _entry("high", 98, 99)
    low = _entry("low", 90, 1)
    assert [x["id"] for x in intelligence.rank([low, high])] == ["high", "low"]


def test_unavailable_high_quality_model_is_excluded():
    intelligence = FreeModelIntelligence()
    intelligence.mark_failure("high", "HTTP 429 quota", 60)
    high = _entry("high", 98)
    low = _entry("low", 90)
    assert [x["id"] for x in intelligence.rank([high, low])] == ["low"]


def test_success_restores_model_availability():
    intelligence = FreeModelIntelligence()
    intelligence.mark_failure("high", "HTTP 429 quota", 60)
    intelligence.mark_success("high")
    assert intelligence.health("high").available is True
    assert intelligence.rank([_entry("high", 98), _entry("low", 90)])[0]["id"] == "high"


def test_non_free_and_non_json_models_are_never_selected():
    intelligence = FreeModelIntelligence()
    paid = _entry("paid", 100)
    paid["free"] = False
    no_json = _entry("no-json", 99)
    no_json["json_capable"] = False
    good = _entry("good", 90)
    assert [x["id"] for x in intelligence.rank([paid, no_json, good])] == ["good"]


def test_production_half_open_probe_reopens_recoverable_health(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    state.write_text(
        """{
          "models": {
            "groq:model-a": {
              "failures": 2,
              "disabled_until": 4102444800,
              "last_error": "rate_limit",
              "last_success": 0
            }
          },
          "providers": {}
        }""",
        encoding="utf-8",
    )
    monkeypatch.setenv("RADAR_PRODUCTION_MODE", "1")
    intelligence = FreeModelIntelligence(state, persist=True)
    ranked = intelligence.rank([{
        **_entry("groq:model-a", 90),
        "family": "groq",
        "deployment_id": "groq:model-a",
    }])
    assert len(ranked) == 1
    assert ranked[0]["availability"] == "recovery_probe"
    assert ranked[0]["_health_recovery_probe"] is True


def test_production_half_open_probe_preserves_blocked_health(tmp_path, monkeypatch):
    state = tmp_path / "llm_health.json"
    state.write_text(
        """{
          "models": {
            "groq:model-a": {
              "failures": 1,
              "disabled_until": 4102444800,
              "last_error": "auth",
              "last_success": 0
            }
          },
          "providers": {}
        }""",
        encoding="utf-8",
    )
    monkeypatch.setenv("RADAR_PRODUCTION_MODE", "1")
    intelligence = FreeModelIntelligence(state, persist=True)
    assert intelligence.rank([{
        **_entry("groq:model-a", 90),
        "family": "groq",
        "deployment_id": "groq:model-a",
    }]) == []
