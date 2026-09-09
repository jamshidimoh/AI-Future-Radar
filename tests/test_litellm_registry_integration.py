import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import free_model_registry as registry
import llm_router_light as router


def test_litellm_deployments_are_registry_driven(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.delenv("KIRAAI_API_KEY", raising=False)
    monkeypatch.delenv("RADAR_ENABLE_GEMINI_FALLBACK", raising=False)
    monkeypatch.delenv("RADAR_ENABLE_HF_FALLBACK", raising=False)
    router._CHAIN_CACHE = None
    registry.build_production_chain(router)
    rows = router._litellm_model_list()
    ids = [row["model_info"]["id"] for row in rows]
    models = [row["litellm_params"]["model"] for row in rows]
    route_names = [row["model_name"] for row in rows]

    assert ids
    assert ids[0] == "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free"
    assert models[0] == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert route_names == [f"radar-production-{i}" for i in range(1, len(rows) + 1)]
    assert "groq/openai/gpt-oss-120b" in models
    assert "groq/qwen/qwen3.6-27b" in models
    assert all(row["litellm_params"]["model"] for row in rows)


def test_litellm_registry_never_adds_uncredentialed_deployments(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.delenv("KIRAAI_API_KEY", raising=False)
    registry.build_production_chain(router)
    rows = router._litellm_model_list()
    assert all(not row["model_info"]["id"].startswith("groq:") for row in rows)
