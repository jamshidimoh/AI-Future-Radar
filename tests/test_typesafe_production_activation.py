from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "run.yml"


def test_production_workflow_activates_typesafe_reranking():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}' in text
    assert 'AI_RADAR_TYPESAFE_RERANK_MODE: active' in text
    assert 'AI_RADAR_TYPESAFE_RERANK_WEIGHT: 0.20' in text
