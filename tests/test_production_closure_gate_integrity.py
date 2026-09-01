from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "production-closure-gate.yml"


def test_closure_gate_does_not_certify_when_logs_are_unavailable():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "class NoRedirect" in text
    assert "GitHub log redirect did not include a Location header" in text
    assert "production evidence logs are incomplete; cannot certify closure" in text
    assert "sys.exit(1)" in text


def test_closure_gate_requires_complete_window_for_all_run_checks():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'return len(logs) == len(window) and all(' in text
    assert "if log_errors or len(logs) != len(window):" in text


def test_closure_gate_blocks_unresolved_evidence_with_failure_status():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = 'print("CLOSURE: BLOCKED — unresolved evidence:", ", ".join(blocked))'
    start = text.index(marker)
    assert "sys.exit(1)" in text[start:start + 400]
