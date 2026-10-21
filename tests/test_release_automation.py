from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-container.yml"
RELEASE_NOTES = ROOT / "docs" / "releases" / "v1.1.0.md"


def test_stable_v1_1_release_is_gated_by_successful_production_closure():
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert 'workflows: ["Production Closure Gate"]' in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "type=raw,value=v1.1.0" in workflow
    assert "gh release create v1.1.0" in workflow
    assert "--target \"$RELEASE_SHA\"" in workflow
    assert "--notes-file docs/releases/v1.1.0.md" in workflow
    assert "Reserve v1.1.0 for a successful closure only" in workflow


def test_v1_1_release_notes_keep_live_acceptance_as_a_prerequisite():
    notes = RELEASE_NOTES.read_text(encoding="utf-8")
    assert "three consecutive successful live production runs" in notes
    assert "confirmed Telegram delivery" in notes
    assert "unverified scrape sources remain ineligible" in notes
    assert "medical/clinical-led" in notes
