from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_telegram_channels_are_style_references_not_content_sources():
    content = (ROOT / "config" / "editorial_inspiration.yaml").read_text(encoding="utf-8")
    # YAML permits quoted and unquoted scalar strings; normalize quotes for this
    # lightweight policy-contract check so it tests semantics, not presentation.
    content = content.replace('"', "")
    for expected in (
        "evidence_authority: none",
        "direct_content_ingestion: false",
        "verbatim_copying: false",
        "primary_source_revalidation_required: true",
        "MrArtificialintelligence",
        "NextBrain_ir",
        "silicon_brain",
        "sharifgpt",
        "Digiato",
        "reference_mode: style_only",
        "reference_mode: limited_style_reference",
    ):
        assert expected in content


def test_telegram_style_references_are_not_registered_as_live_rss_sources():
    files = [
        ROOT / "config" / "sources.yaml",
        ROOT / "config" / "radar_rss_sources.yaml",
        ROOT / "config" / "anthropic_rss_sources.yaml",
    ]
    for path in files:
        raw = path.read_text(encoding="utf-8").casefold()
        assert "t.me/" not in raw
