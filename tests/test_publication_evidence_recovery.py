from fetch_youtube import _normalize_video_result
from summarize import _VALUE_REPAIR_PROMPT, _normalize, _source_text


def test_priority_long_form_channel_enriches_description_with_transcript(monkeypatch):
    calls = []

    def fake_transcript(video_id):
        calls.append(video_id)
        return "The transcript contains the concrete technical evidence."

    monkeypatch.setattr("fetch_youtube._get_transcript_snippet", fake_transcript)
    channel = {
        "name": "Dwarkesh Patel",
        "tier": 1,
        "category": "ai",
        "type": "youtube",
        "official": True,
    }
    item = {
        "title": "A substantial AI interview",
        "video_id": "abc123",
        "summary": "A real description with substantive context.",
        "link": "https://example.com/watch?v=abc123",
        "published": "2026-09-01T08:00:00Z",
    }

    result = _normalize_video_result(channel, item)

    assert result is not None
    assert calls == ["abc123"]
    assert result["evidence_source"] == "channel_page_description+transcript"
    assert "A real description with substantive context." in result["evidence_text"]
    assert "concrete technical evidence" in result["evidence_text"]


def test_source_text_deduplicates_available_evidence_fields():
    item = {
        "summary": "same evidence",
        "evidence_text": "same evidence",
        "description": "additional context",
    }
    source = _source_text(item)
    assert source.count("same evidence") == 1
    assert "additional context" in source


def test_key_quote_can_be_recovered_from_transcript_evidence():
    item = {
        "category": "ai",
        "title": "خبر فارسی",
        "summary": "توضیح منبع",
        "evidence_text": "Transcript quote from the interview.",
    }
    data = {
        "title": "تیتر فارسی",
        "summary": "خلاصه فارسی معتبر با جزئیات کافی.",
        "why_it_matters": "پیامد مشخص و مبتنی بر شواهد منبع.",
        "speakers": "",
        "key_quote": "Transcript quote from the interview.",
    }
    normalized = _normalize(data, item)
    assert normalized["key_quote"] == "Transcript quote from the interview."


def test_value_repair_prompt_matches_editorial_contract():
    assert "3 تا 5 جمله" in _VALUE_REPAIR_PROMPT
    assert "3 تا 4 جمله" in _VALUE_REPAIR_PROMPT
    assert "جزئیات فنی" in _VALUE_REPAIR_PROMPT
