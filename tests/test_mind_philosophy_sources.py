from pathlib import Path

import yaml

from src.source_authority import resolve_google_news_tier, resolve_source_tier

ROOT = Path(__file__).resolve().parents[1]


def _load_registry():
    path = ROOT / "config" / "mind_philosophy_sources.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_authoritative_philosophy_sources_are_tier1():
    assert resolve_source_tier(source_name="Stanford Encyclopedia of Philosophy", source_url="https://plato.stanford.edu/entries/artificial-intelligence/") == 1
    assert resolve_source_tier(source_name="Cambridge University Press", source_url="https://www.cambridge.org/core/books/cambridge-handbook-of-the-law-ethics-and-policy-of-artificial-intelligence/philosophy-of-ai/EA114E662BF42641EA9720228D69407B") == 1
    assert resolve_source_tier(source_name="Oxford Academic", source_url="https://academic.oup.com/edited-volume/59762/chapter-abstract/515781959") == 1
    assert resolve_google_news_tier("Stanford Encyclopedia of Philosophy", "https://plato.stanford.edu/entries/artificial-intelligence/") == 1


def test_discovery_and_frontier_sources_are_not_promoted_to_authority():
    registry = _load_registry()
    roles = registry["source_roles"]
    assert roles["index"]["authority"] == 3
    assert roles["index"]["publication_eligible"] is False
    assert roles["frontier_discussion"]["authority"] == 3
    assert roles["frontier_discussion"]["publication_eligible"] is False

    by_name = {source["name"]: source for source in registry["sources"]}
    for name in ("PhilPapers", "PhilSci-Archive", "The Brains Blog", "LessWrong"):
        assert by_name[name]["normal_publication"] is False
        assert by_name[name]["role"] in {"index", "frontier_discussion"}


def test_lane_requires_ai_bridge_and_has_no_arxiv_dependency():
    registry = _load_registry()
    assert registry["lane"]["mission_area"] == "mind_cognition"
    assert registry["lane"]["bridge_required"] is True
    text = (ROOT / "config" / "mind_philosophy_sources.yaml").read_text(encoding="utf-8").casefold()
    assert "arxiv.org" not in text
