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
    assert "and is_completed_production_attempt(r)" in text
    assert "is_completed_production_attempt," in text


def test_closure_gate_is_code_pinned_and_window_checks_are_per_run():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "def code_fingerprint(sha):" in text
    assert "dynamic_runtime_paths = {\"config/free_model_registry.yaml\"}" in text
    assert "non_runtime_paths = {" in text
    assert 'path.startswith("docs/")' in text
    assert 'path.startswith("digital_transformation_booklet/")' in text
    assert '"tests/test_production_closure_gate_integrity.py"' in text
    assert '"scripts/production_closure_contract.py"' in text
    assert '"tests/test_production_closure_contract.py"' in text
    assert "or is_non_runtime" in text
    assert "startsWith(" not in text
    assert "if len(distinct_fingerprints) != 1:" in text
    assert "def all_runs(pattern):" in text
    assert "return all(has(logs[r[\"run_number\"]], pattern) for r in window)" in text
    assert "if log_errors or len(logs) != 3:" in text


def test_closure_gate_uses_shared_strict_publication_evidence_contract():
    text = WORKFLOW.read_text(encoding="utf-8")
    helper = (WORKFLOW.parents[2] / "scripts" / "production_closure_contract.py").read_text(encoding="utf-8")
    assert "from scripts.production_closure_contract import (" in text
    assert "is_persisted_state_skip," in text
    assert "publish_evidence," in text
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



def test_closure_gate_requires_people_bootstrap_and_fresh_llm_health():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"14_people_bootstrap_30_deliveries": people_bootstrap_complete' in text
    assert '"15_llm_health_fresh_for_latest_run": health_state_current' in text
    assert "people_bootstrap_state_complete" in text
    assert "health_snapshot_fresh" in text



def test_production_runs_are_serialized_without_canceling_active_attempts():
    run_workflow = WORKFLOW.parent / "run.yml"
    text = run_workflow.read_text(encoding="utf-8")
    assert "ai-future-radar-state-only" in text
    assert "ai-future-radar-production" in text
    assert "github.event_name == 'push'" in text
    assert "chore: persist production state [skip ci]" in text
    assert "cancel-in-progress: false" in text
