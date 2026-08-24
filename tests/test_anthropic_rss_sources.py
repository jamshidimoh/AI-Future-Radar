from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import fetch_rss
from scripts import audit_rss_sources


def test_anthropic_rss_registry_is_explicitly_unofficial_and_unique():
    path = ROOT / "config" / "anthropic_rss_sources.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = config["rss_sources"]

    assert len(sources) == 2
    assert len({source["url"].rstrip("/") for source in sources}) == 2
    assert all(source["official"] is False for source in sources)
    assert {source["name"] for source in sources} == {
        "Anthropic News (community RSS)",
        "Anthropic Engineering (community RSS)",
    }


def test_anthropic_sources_merge_without_duplicate_urls():
    base = [{
        "name": "Anthropic News (community RSS)",
        "url": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",
        "tier": 1,
        "type": "community_rss",
        "content_type": "official",
        "official": False,
    }]
    merged = fetch_rss._merge_rss_sources(base)
    urls = [source["url"].rstrip("/") for source in merged]
    assert len(urls) == len(set(urls))
    assert any("anthropic_engineering_rss.xml" in url for url in urls)


def test_rss_audit_loads_supplemental_sources_without_duplicates():
    sources = audit_rss_sources._load_sources()
    names = {source["name"] for source in sources}
    urls = [source["url"].rstrip("/") for source in sources]
    assert "Anthropic News (community RSS)" in names
    assert "Anthropic Engineering (community RSS)" in names
    assert len(urls) == len(set(urls))
