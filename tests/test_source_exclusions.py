from pathlib import Path

import yaml

from src.source_exclusions import is_excluded_source_text, is_excluded_source_url
from src.fetch_google_news import _collect_query
from src.fetch_rss import _merge_rss_sources

ROOT = Path(__file__).resolve().parents[1]


def test_excluded_source_url_is_blocked():
    assert is_excluded_source_url("https://arxiv.org/abs/1234.5678")
    assert is_excluded_source_url("https://export.arxiv.org/rss/cs.AI")
    assert not is_excluded_source_url("https://openai.com/research")


def test_excluded_source_query_is_not_searched():
    assert is_excluded_source_text("site:arxiv.org AI research")
    _, items, error = _collect_query(
        {"query": "site:arxiv.org AI research", "category": "ai"},
        0,
    )
    assert items == []
    assert error is None


def test_excluded_rss_source_is_removed_before_fetch():
    sources = [
        {"name": "arXiv", "url": "https://export.arxiv.org/rss/cs.AI"},
        {"name": "OpenAI", "url": "https://openai.com/news/rss.xml"},
    ]
    merged = _merge_rss_sources(sources)
    names = [item["name"] for item in merged]
    assert "OpenAI" in names
    assert all("arxiv" not in str(name).lower() for name in names)


def test_accidental_excluded_result_is_rejected():
    assert is_excluded_source_url("https://arxiv.org/abs/9999.0001")


def test_production_source_registry_contains_no_excluded_source():
    payload = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8")) or {}
    for source in payload.get("rss_sources", []):
        assert not is_excluded_source_url(source.get("url"))
        assert not is_excluded_source_text(source.get("name"))
    for query in payload.get("google_news_queries", []):
        assert not is_excluded_source_text(query.get("query"))


def test_supplemental_rss_registry_contains_no_excluded_source():
    path = ROOT / "config" / "radar_rss_sources.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    for source in (payload or {}).get("rss_sources", []):
        assert not is_excluded_source_url(source.get("url"))
        assert not is_excluded_source_text(source.get("name"))
