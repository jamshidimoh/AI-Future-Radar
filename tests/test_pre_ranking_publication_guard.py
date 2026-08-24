from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import period_ranked_pipeline as pipeline


def test_pre_ranking_guard_excludes_canonical_and_high_confidence_semantic_conflicts(monkeypatch):
    records = [
        {
            "title": "Old exact story",
            "summary": "an unrelated old summary",
            "link": "https://example.com/exact",
        },
        {
            "title": "Andrew Ng launches a new AI agents course",
            "summary": "A new course teaches developers how to build AI agents.",
            "link": "https://example.com/old-course",
        },
    ]
    monkeypatch.setattr(pipeline, "_load_records", lambda: records)

    def fake_semantic_conflict(title, summary, record):
        # Only the Andrew Ng candidate is a high-confidence semantic match.
        if "Andrew Ng" in summary and record.get("title", "").startswith("Andrew Ng"):
            return 0.95
        return 0.0

    monkeypatch.setattr(pipeline, "_semantic_conflict", fake_semantic_conflict)

    items = [
        {"title": "New wording", "summary": "fresh material", "link": "https://example.com/exact"},
        {
            "title": "New developer program teaches practical AI agent building",
            "summary": "Andrew Ng's course focuses on building AI agents for developers.",
            "link": "https://another.example/course",
        },
        {"title": "A genuinely new AI story", "summary": "A different development.", "link": "https://example.com/new"},
    ]

    kept = pipeline._exclude_published_candidates(items)

    assert [x["title"] for x in kept] == ["A genuinely new AI story"]
