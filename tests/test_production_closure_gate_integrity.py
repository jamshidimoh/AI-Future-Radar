from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "production-closure-gate.yml"


def test_closure_gate_does_not_certify_when_logs_are_unavailable():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "class NoRedirect" in text
    assert "GitHub log redirect did not include a Location header" in text
    assert "production evidence logs are incomplete; cannot certify closure" in text
    assert "sys.exit(1)" in text


def test_closure_gate_requires_three_executable_runs_as_a_failure_until_closed():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "if len(executable) < 3:"
    start = text.index(marker)
    block = text[start:start + 300]
    assert "3 required" in block
    assert "sys.exit(1)" in block


def test_closure_gate_is_code_pinned_and_window_checks_are_per_run():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "def code_fingerprint(sha):" in text
    assert "startsWith(" not in text
    assert "if len(distinct_fingerprints) != 1:" in text
    assert "def all_runs(pattern):" in text
    assert "return all(has(logs[r[\"run_number\"]], pattern) for r in window)" in text
    assert "if log_errors or len(logs) != 3:" in text


def test_closure_gate_uses_runtime_acceptance_for_zero_publish():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "fail_closed_acceptance = has(text, r\"\\[Production Acceptance\\] PASS:\\s+production acceptance PASS:\\s+fail-closed\")" in text
    assert "return zero_publish and acceptance and fail_closed_acceptance and publication_attempted" in text
    assert "[Fail-Closed Acceptance Evidence] PASS" not in text


def test_closure_gate_blocks_unresolved_evidence_with_failure_status():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = 'print("CLOSURE: BLOCKED — unresolved evidence:", ", ".join(blocked))'
    start = text.index(marker)
    assert "sys.exit(1)" in text[start:start + 400]


def test_closure_gate_has_no_push_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\n  push:" not in text
