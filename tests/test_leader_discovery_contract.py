from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_sam_altman_has_direct_interview_discovery_query():
    watch = yaml.safe_load((ROOT / "config" / "leader_watchlist.yaml").read_text(encoding="utf-8"))
    queries = watch.get("google_news_queries", [])
    assert any(
        q.get("watch_person") == "Sam Altman"
        and q.get("content_type") == "interview"
        and "AGI" in str(q.get("query", ""))
        for q in queries
    )


def test_direct_leader_podcast_feed_exists():
    sources = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    rss = sources.get("rss_sources", [])
    match = [x for x in rss if x.get("name") == "David Senra"]
    assert len(match) == 1
    assert match[0]["tier"] == 1
    assert match[0]["content_type"] == "interview"
    assert match[0]["official"] is True
    assert "feeds.megaphone.fm" in match[0]["url"]
