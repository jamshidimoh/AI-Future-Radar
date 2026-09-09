from pathlib import Path

from src import free_model_registry as registry


def test_registry_is_quality_first_and_contains_current_top_candidates():
    entries = registry.ranked_entries()
    ids = [e["id"] for e in entries]
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in ids
    assert "nvidia/nemotron-3-super-120b-a12b:free" in ids
    assert "google/gemma-4-31b-it:free" in ids
    assert "openai/gpt-oss-20b:free" in ids
    scores = [e["effective_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_registry_excludes_hf_from_primary_models_and_runtime_adds_it_last():
    chain = registry.build_production_chain(__import__("src.llm_router_light", fromlist=["x"]))
    names = [name for name, _ in chain]
    assert names[-2:] == ["Gemini", "HuggingFace"]


def test_registry_file_exists():
    assert (Path(__file__).resolve().parents[1] / "config" / "free_model_registry.yaml").exists()
