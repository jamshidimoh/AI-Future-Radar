import time
from unittest.mock import patch

import period_ranked_pipeline as ranking


def _item(title, source, score):
    return {
        "title": title,
        "summary": "A verified development in artificial intelligence research.",
        "content_type": "news",
        "source": source,
        "editorial_score": score,
        "published": "2026-08-22",
    }


def test_source_cap_is_enforced():
    items = [
        *[_item(f"Community {i}", "Reddit", 100 - i) for i in range(5)],
        *[_item(f"Research {i}", "Research Institute", 80 - i) for i in range(3)],
        *[_item(f"University {i}", "University Lab", 70 - i) for i in range(3)],
    ]
    with patch.object(ranking, "_load_records", return_value=[]), patch.object(
        ranking._pipeline, "load_source_history", return_value=[]
    ):
        selected = ranking._global_ranked_selection(
            items, max_posts=4, max_per_source=2, max_per_type=4, policy={"rotation_days": 7}
        )
    counts = {}
    for item in selected:
        counts[item["source"]] = counts.get(item["source"], 0) + 1
    assert len(selected) == 4
    assert "Reddit" not in counts
    assert all(value <= 2 for value in counts.values())


def test_recent_community_source_is_excluded_while_fresh_authoritative_sources_backfill():
    items = [
        _item("Community recent 1", "Reddit", 100),
        _item("Community recent 2", "Reddit", 99),
        _item("Research fresh 1", "Research Institute", 90),
        _item("Research fresh 2", "Research Institute", 89),
        _item("University fresh 1", "University Lab", 88),
        _item("University fresh 2", "University Lab", 87),
    ]
    recent_ts = time.time() - 3600
    history = [
        {"ts": recent_ts, "source": "Reddit", "content_type": "news"},
        {"ts": recent_ts + 1, "source": "Reddit", "content_type": "news"},
    ]
    with patch.object(ranking, "_load_records", return_value=[]), patch.object(
        ranking._pipeline, "load_source_history", return_value=history
    ):
        selected = ranking._global_ranked_selection(
            items, max_posts=4, max_per_source=2, max_per_type=4, policy={"rotation_days": 7}
        )
    sources = [item["source"] for item in selected]
    assert len(selected) == 4
    assert sources[:2] == ["Research Institute", "University Lab"]
    assert "Reddit" not in sources
    assert sources.count("Research Institute") == 2
    assert sources.count("University Lab") == 2
