import json
from pathlib import Path

import src.ranking_audit as audit


def test_audit_records_canonical_fields_without_mutating_item(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "ranking_audit.jsonl")
    monkeypatch.setattr(audit, "SUMMARY_PATH", tmp_path / "ranking_audit_summary.json")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "44")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    item = {
        "title": "Evidence-rich model release",
        "link": "https://example.com/story",
        "source": "Official Lab",
        "source_tier": 1,
        "content_type": "product_news",
        "period_rank": 1,
        "normal_period_rank": 1,
        "final_editorial_score": 88.4,
        "editorial_score_pre_signal": 90,
        "signal_score": 83,
        "signal_vector": {"evidence_strength": 9, "novelty": 8},
        "model_release_priority": True,
        "model_release_bonus_legacy": 15,
        "_rank_is_tier0": False,
    }
    before = dict(item)

    path = audit.audit_selection([item])

    assert item == before
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["schema_version"] == "ranking-audit.v1"
    assert row["run_id"] == "123"
    assert row["canonical_rank_score"] == 88.4
    assert row["editorial_score"] == 90.0
    assert row["signal_score"] == 83.0
    assert row["signal_vector"]["evidence_strength"] == 9.0
    assert row["legacy_model_bonus"] == 15.0
    assert row["reason_codes"] == ["model_release"]


def test_audit_summary_is_run_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "ranking_audit.jsonl")
    monkeypatch.setattr(audit, "SUMMARY_PATH", tmp_path / "ranking_audit_summary.json")
    monkeypatch.setenv("GITHUB_RUN_ID", "999")
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "77")
    monkeypatch.setenv("GITHUB_SHA", "def456")

    audit.audit_selection([])
    summary = json.loads((tmp_path / "ranking_audit_summary.json").read_text(encoding="utf-8"))

    assert summary["run_id"] == "999"
    assert summary["run_number"] == "77"
    assert summary["commit_sha"] == "def456"
    assert summary["record_count"] == 0
