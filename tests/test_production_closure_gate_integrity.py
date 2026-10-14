from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "production-closure-gate.yml"


def test_closure_gate_does_not_certify_when_logs_are_unavailable():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "class NoRedirect" in text
    assert "GitHub log redirect did not include a Location header" in text
    assert "production evidence logs are incomplete; cannot certify closure" in text
    assert "sys.exit(1)" in text


def test_closure_gate_requires_three_consecutive_production_attempts():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "if len(attempted) < 3:"
    start = text.index(marker)
    block = text[start:start + 400]
    assert "consecutive production attempts observed; 3 required" in block
    assert "sys.exit(1)" in block
    assert 'if run.get("conclusion") != "success" or not bot or bot.get("conclusion") != "success":' in text
    assert "Every non-state-only production invocation occupies a place in the" in text
    assert "is_persisted_state_skip(run, bot)" in text


def test_closure_gate_is_code_pinned_and_window_checks_are_per_run():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "def code_fingerprint(sha):" in text
    assert 'fingerprint_excluded_paths = {"config/free_model_registry.yaml", "docs/PRODUCTION_CLOSURE_STATUS.md", "tests/test_production_closure_gate_integrity.py"}' in text
    assert "updated_status = put_json(" in text
    assert '"/contents/docs/PRODUCTION_CLOSURE_STATUS.md"' in text
    assert "CLOSED / PRODUCTION BASELINE" in text
    assert "FINAL_STATUS_DOC:" in text
    assert "contents: write" in text
    assert "startsWith(" not in text
    assert "if len(distinct_fingerprints) != 1:" in text
    assert "def all_runs(pattern):" in text
    assert "return all(has(logs[r[\"run_number\"]], pattern) for r in window)" in text
    assert "if log_errors or len(logs) != 3:" in text


def test_closure_gate_uses_shared_strict_publication_evidence_contract():
    text = WORKFLOW.read_text(encoding="utf-8")
    helper = (WORKFLOW.parents[2] / "scripts" / "production_closure_contract.py").read_text(encoding="utf-8")
    assert "from scripts.production_closure_contract import is_persisted_state_skip, publish_evidence" in text
    assert "per_run_publish = {r[\"run_number\"]: publish_evidence(logs[r[\"run_number\"]]) for r in window}" in text
    assert "selected == 0" in helper
    assert "sent > 0" in helper
    assert r"\[Telegram Published\]" in helper
    assert "return zero_candidate_run" in helper
    assert "fail_closed_acceptance = has(text" not in text


def test_closure_gate_blocks_unresolved_evidence_with_failure_status():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = 'print("CLOSURE: BLOCKED — unresolved evidence:", ", ".join(blocked))'
    start = text.index(marker)
    assert "sys.exit(1)" in text[start:start + 400]


def test_closure_gate_has_no_push_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\n  push:" not in text

def test_closure_gate_embedded_python_compiles():
    import yaml

    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["closure-evidence"]["steps"]
    evaluation = next(step for step in steps if step.get("name") == "Evaluate production evidence")
    run = evaluation["run"]
    marker = "python - <<'PY'\\n"
    assert marker in run
    script = run.split(marker, 1)[1].rsplit("\\nPY", 1)[0]
    compile(script, str(WORKFLOW), "exec")

