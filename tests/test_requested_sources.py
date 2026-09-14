from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _sources(path):
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(item.get("name")): item for item in payload.get("rss_sources", []) if isinstance(item, dict)}


def test_requested_rss_sources_are_registered_without_arxiv_or_reddit():
    sources = _sources(ROOT / "config" / "radar_rss_sources.yaml")
    expected = {
        "Techmeme": "https://www.techmeme.com/feed.xml",
        "TechCrunch": "https://techcrunch.com/feed/",
        "The Verge - AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "The Rundown AI": "https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml",
        "TLDR AI": "https://tldr.tech/api/rss/ai",
        "Hacker News": "https://news.ycombinator.com/rss",
    }
    for name, url in expected.items():
        assert sources[name]["url"] == url
    assert not any("arxiv.org" in str(item.get("url", "")).lower() for item in sources.values())


def test_hugging_face_papers_is_registered_as_curated_discovery():
    payload = yaml.safe_load((ROOT / "config" / "radar_google_news_queries.yaml").read_text(encoding="utf-8")) or {}
    queries = {str(item.get("name")): item for item in payload.get("google_news_queries", []) if isinstance(item, dict)}
    hf = queries["Hugging Face Papers"]
    assert "site:huggingface.co/papers" in hf["query"]
    assert hf["preferred_source"] == "Hugging Face Papers"
    assert hf["content_type"] == "research"
