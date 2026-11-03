import yaml
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_telegram_channels_are_style_references_not_content_sources():
    policy = yaml.safe_load(
        (ROOT / "config" / "editorial_inspiration.yaml").read_text(encoding="utf-8")
    )
    assert policy["policy"]["evidence_authority"] == "none"
    assert policy["policy"]["direct_content_ingestion"] is False
    assert policy["policy"]["verbatim_copying"] is False
    assert policy["policy"]["primary_source_revalidation_required"] is True

    channels = {item["handle"]: item for item in policy["channels"]}
    assert {
        "MrArtificialintelligence",
        "NextBrain_ir",
        "silicon_brain",
        "sharifgpt",
        "Digiato",
    } <= set(channels)
    assert all(
        item["reference_mode"] in {"style_only", "limited_style_reference"}
        for item in channels.values()
    )


def test_telegram_style_references_are_not_registered_as_live_rss_sources():
    files = [
        ROOT / "config" / "sources.yaml",
        ROOT / "config" / "radar_rss_sources.yaml",
        ROOT / "config" / "anthropic_rss_sources.yaml",
    ]
    for path in files:
        raw = path.read_text(encoding="utf-8").casefold()
        assert "t.me/" not in raw
