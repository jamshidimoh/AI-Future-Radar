from datetime import datetime, timezone

from radar_models import CanonicalContent, Evidence, SourceItem, Story


def test_source_item_has_stable_discovery_contract():
    item = SourceItem(
        source_id="reuters:1",
        source_name="Reuters",
        url="https://example.com/story",
        title="AI story",
        published_at=datetime.now(timezone.utc),
    )
    assert item.source_name == "Reuters"
    assert item.content_type == "news"


def test_story_is_the_canonical_editorial_unit():
    source = SourceItem(
        source_id="a",
        source_name="A",
        url="https://a.example/story",
        title="Same story",
    )
    evidence = Evidence(
        evidence_id="e1",
        source_url=source.url,
        source_name=source.source_name,
        evidence_type="primary",
        claim="The event happened.",
    )
    story = Story(
        story_id="story-1",
        canonical_title="Same story",
        sources=[source],
        evidence=[evidence],
    )
    assert story.story_id == "story-1"
    assert story.sources[0].url == source.url
    assert story.evidence[0].evidence_type == "primary"


def test_canonical_content_requires_core_publication_fields():
    content = CanonicalContent(
        title="خبر",
        summary="خلاصه",
        why_it_matters="اهمیت",
        source_name="Reuters",
        source_url="https://reuters.example/story",
        chatgpt_url="https://chatgpt.com/?q=story",
        content_type="news",
    )
    assert content.required_fields_present()


def test_canonical_content_rejects_missing_required_field():
    content = CanonicalContent(
        title="خبر",
        summary="خلاصه",
        why_it_matters="اهمیت",
        source_name="Reuters",
        source_url="https://reuters.example/story",
        chatgpt_url="",
        content_type="news",
    )
    assert not content.required_fields_present()
