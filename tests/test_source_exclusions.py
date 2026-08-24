from src.source_exclusions import is_excluded_source_text, is_excluded_source_url
from src.fetch_google_news import _collect_query
from src.fetch_rss import _merge_rss_sources


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
    assert [item["name"] for item in merged] == ["OpenAI"]


def test_accidental_excluded_result_is_rejected():
    assert is_excluded_source_url("https://arxiv.org/abs/9999.0001")
