from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import dedup


REQUIRED_RSS_SOURCES = {
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Google DeepMind Blog": "https://deepmind.google/blog/rss.xml",
    "Google Research Blog": "https://research.google/blog/rss/",
    "BAIR Blog": "https://bair.berkeley.edu/blog/feed.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
}


def _load_sources():
    with (ROOT / "config" / "sources.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_rss_registry_has_unique_urls_and_required_authoritative_sources():
    config = _load_sources()
    sources = config["rss_sources"]
    urls = [source["url"].rstrip("/") for source in sources]
    assert len(urls) == len(set(urls))

    by_name = {source["name"]: source for source in sources}
    for name, url in REQUIRED_RSS_SOURCES.items():
        assert by_name[name]["url"] == url
        assert by_name[name]["tier"] == 1
        assert by_name[name]["official"] is True


def test_rss_cross_source_duplicate_remains_blocked_by_canonical_gate():
    items = [
        {
            "title": "Introducing a new AI research model",
            "link": "https://source-a.example/story?id=42",
            "summary": "AI research update.",
            "source": "Source A",
            "category": "ai",
        },
        {
            "title": "Introducing a new AI research model",
            "link": "https://source-b.example/story?id=84",
            "summary": "AI research update.",
            "source": "Source B",
            "category": "ai",
        },
    ]

    assert len(dedup.filter_new_items(items, set())) == 1
