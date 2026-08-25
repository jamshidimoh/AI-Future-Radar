import importlib


def test_production_format_hook_preserves_main_formatter_contract(monkeypatch):
    module = importlib.import_module("scripts.production_with_ranking_audit")
    captured = {}

    def fake_pipeline_main(hooks=None):
        captured["hooks"] = hooks or {}
        formatter = captured["hooks"]["format_post"]
        payload = formatter(
            {"title": "عنوان آزمون", "summary": "خلاصه آزمون", "why_it_matters": "اهمیت"},
            "منبع آزمون",
            "https://example.com/story",
            content_type="news",
            published="2026-08-25",
            source_type="news",
            source_tier=1,
            leader="",
        )
        assert payload

    monkeypatch.setattr(module, "_original_main", fake_pipeline_main)
    module._audited_main(hooks={})

    assert "format_post" in captured["hooks"]
