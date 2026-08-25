from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_state_persistence_runs_after_upstream_failure():
    workflow = (ROOT / ".github" / "workflows" / "run.yml").read_text(encoding="utf-8")
    marker = "- name: Persist production state"
    start = workflow.index(marker)
    block = workflow[start : workflow.index("- name: Upload production diagnostics", start)]
    assert "if: always()" in block
    assert "git add data/seen.json" in block
