from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_reads_strict_relevance_from_policy():
    text = (ROOT / "period_ranked_pipeline.py").read_text(encoding="utf-8")
    assert 'policy.get("strict_relevance", False)' in text
    assert "strict_relevance=strict_relevance" in text
