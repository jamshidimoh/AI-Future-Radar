import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from free_model_evidence import benchmark_record, benchmark_score, normalize_model_id, quality_score


def test_normalize_free_variant_id():
    assert normalize_model_id("nvidia/nemotron-3-ultra-550b-a55b:free") == "nvidia/nemotron-3-ultra-550b-a55b"


def test_benchmark_score_uses_available_dimensions():
    score = benchmark_score({"intelligence_index": 90, "agentic_index": 80, "coding_index": 70})
    assert score == 85.0


def test_benchmark_record_normalizes_openrouter_evidence():
    row = benchmark_record({
        "source": "artificial-analysis",
        "model_permaslug": "openai/gpt-oss-120b",
        "intelligence_index": 45.0,
        "agentic_index": 38.0,
        "coding_index": 50.0,
    })
    assert row["benchmark_model_id"] == "openai/gpt-oss-120b"
    assert row["benchmark_source"] == "artificial-analysis"
    assert row["coding_index"] == 50.0


def test_quality_score_does_not_promote_unknown_quality_above_evidenced_model():
    evidenced = {
        "intelligence_index": 70,
        "agentic_index": 60,
        "coding_index": 50,
        "task_fit": 75,
        "reliability_score": 90,
    }
    unknown = {"task_fit": 20, "reliability_score": 90}
    assert quality_score(evidenced) > quality_score(unknown)
