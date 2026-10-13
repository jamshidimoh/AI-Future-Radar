from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "production-closure-gate.yml"


def test_closure_gate_does_not_certify_when_logs_are_unavailable():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "class NoRedirect" in text
    assert "GitHub log redirect did not include a Location header" in text
    assert "production evidence logs are incomplete; cannot certify closure" in text
    assert "sys.exit(1)" in text


def test_closure_gate_requires_three_consecutive_runtime_attempts_and_blocks_failures():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "if len(runtime_attempts) < 3:"
    start = text.index(marker)
    block = text[start:start + 450]
    assert "3 required" in block
    assert "sys.exit(1)" in block
    assert "if failed_runtime_attempts:" in text
    assert "latest three consecutive production runtime attempts include failures" in text


def test_closure_gate_is_code_pinned_and_window_checks_are_per_run():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "def code_fingerprint(sha):" in text
    assert "dynamic_runtime_paths = {\"config/free_model_registry.yaml\"}" in text
    assert "startsWith(" not in text
    assert "if len(distinct_fingerprints) != 1:" in text
    assert "def all_runs(pattern):" in text
    assert "return all(has(logs[r[\"run_number\"]], pattern) for r in window)" in text
    assert "if log_errors or len(logs) != 3:" in text


def test_closure_gate_allows_zero_publish_only_for_explicitly_empty_selection():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if final_budget:" in text
    assert "selected_count = final_selection[-1] if final_selection else (" in text
    assert r"\[Publication Summary Budget\].*\boutput=0\b" in text
    assert "final_budget = re.findall(" in text
    assert r"\[Production Selection\][^\n]*\btotal=(\d+)" in text
    assert "no_selected_candidates = int(final_budget[-1]) == 0" in text
    assert "return zero_publish and no_selected_candidates and acceptance" in text
    assert "fail_closed_acceptance" not in text
    assert "publication_attempted" not in text


def test_closure_gate_blocks_unresolved_evidence_with_failure_status():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = 'print("CLOSURE: BLOCKED — unresolved evidence:", ", ".join(blocked))'
    start = text.index(marker)
    assert "sys.exit(1)" in text[start:start + 400]


def test_closure_gate_has_no_push_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\n  push:" not in text


def test_closure_gate_zero_publish_evidence_counts_all_publication_lanes():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "lane_counts = [" in text
    assert "all(value == 0 for value in lane_counts)" in text
    assert r"\b(?:final_news|normal_news|mind_ideas_voices|people|technical_trend|voices_perspectives|strategic_analytical|tier0_news)=(\d+)" in text
    assert r"\[Education Published\].*telegram_delivery=successful" in text
