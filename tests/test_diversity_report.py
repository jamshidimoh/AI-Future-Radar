import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import diversity_report  # noqa: E402


def test_report_counts_mission_area_from_legacy_category(capsys):
    history = [
        {"source": "MarkTechPost", "category": "ai", "content_type": "research"},
        {"source": "MarkTechPost", "category": "ai", "content_type": "research"},
        {"source": "Nature", "category": "mind", "content_type": "research"},
    ]
    diversity_report._report(history)
    out = capsys.readouterr().out
    assert "3 published items" in out
    assert "ai_core" in out
    assert "mind_cognition" in out
    assert "MarkTechPost" in out


def test_load_history_excludes_education_entries(tmp_path, monkeypatch):
    import json
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({"source_history": [
        {"source": "MarkTechPost", "category": "ai", "content_type": "research"},
        {"source": "education", "category": "ai", "content_type": "education"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(diversity_report, "SEEN_PATH", seen_path)
    history = diversity_report._load_history()
    assert len(history) == 1
    assert history[0]["source"] == "MarkTechPost"


def test_report_handles_empty_history(capsys):
    diversity_report._report([])
    out = capsys.readouterr().out
    assert "No non-education publication history" in out


def test_dominant_source_warning_fires_above_threshold(capsys):
    history = [{"source": "MarkTechPost", "category": "ai", "content_type": "research"} for _ in range(8)]
    history += [{"source": "Nature", "category": "ai", "content_type": "research"} for _ in range(2)]
    diversity_report._report(history)
    out = capsys.readouterr().out
    assert "accounts for" in out
