from src.summarize import _is_voice_item, _length_ok, _source_text, _summary_depth


def test_long_source_requires_rich_summary():
    data = {"summary": "کوتاه", "why_it_matters": "کوتاه"}
    assert not _length_ok(data, "x" * 1000)


def test_rich_summary_passes_length_gate():
    data = {"summary": "الف" * 260, "why_it_matters": "ب" * 180}
    assert _length_ok(data, "x" * 1000)

    

def test_expert_voice_gets_dedicated_summary_depth():
    item = {
        "title": "Dwarkesh Podcast with a frontier AI researcher",
        "source": "YouTube - Dwarkesh Patel",
        "content_type": "podcast",
        "mission_area": "ai_core",
        "voice_expert_deep_lane": True,
    }
    assert _is_voice_item(item)
    assert "Expert Voice" in _summary_depth(item)


def test_product_release_uses_status_and_claim_attribution_guidance():
    item = {
        "title": "A new model launch",
        "content_type": "product_news",
        "mission_area": "ai_core",
    }
    depth = _summary_depth(item)
    assert "معرفی محصول/مدل" in depth
    assert "دسترسی عمومی/محدود" in depth
    assert "ادعاهای تبلیغاتی" in depth


def test_research_summary_preserves_method_and_publication_status():
    item = {
        "title": "A new AI study",
        "content_type": "research",
        "mission_area": "ai_core",
    }
    depth = _summary_depth(item)
    assert "مقاله داوری‌شده" in depth
    assert "روش" in depth
    assert "همبستگی را علت" in depth


def test_summary_evidence_context_includes_voice_identity_fields():
    item = {
        "title": "An interview",
        "source": "YouTube - Lex Fridman Podcast",
        "speakers": "Guest Expert",
        "summary": "source description",
        "evidence_text": "transcript evidence",
    }
    evidence = _source_text(item)
    assert "An interview" in evidence
    assert "Guest Expert" in evidence
    assert "transcript evidence" in evidence
