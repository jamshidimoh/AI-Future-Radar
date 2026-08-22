import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import educational_content


def test_lesson_26_adds_current_fallback_sources_without_duplicates(monkeypatch):
    lesson = {"id": 26, "sources": [{"name": "old", "url": "https://old.example/source", "year": 2024}]}
    monkeypatch.setattr(educational_content, "load_source_fallbacks", lambda: {
        "26": [
            {"name": "current", "url": "https://www.nist.gov/document/nist-and-qis-2025", "year": 2025},
            {"name": "current-duplicate", "url": "https://old.example/source", "year": 2024},
        ]
    })
    candidates = educational_content._source_candidates(lesson)
    urls = [item["url"] for item in candidates]
    assert urls.count("https://old.example/source") == 1
    assert "https://www.nist.gov/document/nist-and-qis-2025" in urls


def test_source_candidates_keep_curriculum_sources_as_primary_order(monkeypatch):
    lesson = {"id": 26, "sources": [{"name": "primary", "url": "https://primary.example", "year": 2025}]}
    monkeypatch.setattr(educational_content, "load_source_fallbacks", lambda: {
        "26": [{"name": "fallback", "url": "https://fallback.example", "year": 2025}]
    })
    candidates = educational_content._source_candidates(lesson)
    assert candidates[0]["url"] == "https://primary.example"
    assert candidates[1]["url"] == "https://fallback.example"


def test_unreachable_declared_2025_source_is_not_verified(monkeypatch):
    lesson = {
        "id": 26,
        "a": {"term": "A", "fa": "آ", "seed": "تعریف پایه A"},
        "b": {"term": "B", "fa": "ب", "seed": "تعریف پایه B"},
        "relation": "رابطه",
        "sources": [{"name": "dead", "url": "https://dead.example/source", "year": 2025}],
    }
    monkeypatch.setattr(educational_content, "_source_candidates", lambda _: lesson["sources"])
    monkeypatch.setattr(educational_content, "_fetch_reference", lambda _: ("", None))
    generated, verified = educational_content._generate(lesson)
    assert generated is None
    assert verified == []


def test_retrieved_2025_source_is_verified_even_when_declared_year_missing(monkeypatch):
    lesson = {
        "id": 26,
        "a": {"term": "A", "fa": "آ", "seed": "تعریف پایه A"},
        "b": {"term": "B", "fa": "ب", "seed": "تعریف پایه B"},
        "relation": "رابطه",
        "sources": [{"name": "current", "url": "https://current.example/source"}],
    }
    monkeypatch.setattr(educational_content, "_source_candidates", lambda _: lesson["sources"])
    monkeypatch.setattr(educational_content, "_fetch_reference", lambda _: ("محتوای معتبر 2025", 2025))
    monkeypatch.setattr(educational_content, "call_llm_with_fallback", lambda *args, **kwargs: ('{"term_a_definition":"تعریف A معتبر و کافی است","term_a_simple":"توضیح ساده A معتبر است","term_b_definition":"تعریف B معتبر و کافی است","term_b_simple":"توضیح ساده B معتبر است","relationship":"رابطه معتبر میان A و B","example":"مثال معتبر و روشن برای هر دو مفهوم است","takeaway":"نکته کاربردی و معتبر برای یادگیری"}', 'test'))
    monkeypatch.setattr(educational_content, "get_quality_chain", lambda: ["test"])
    generated, verified = educational_content._generate(lesson)
    assert generated is not None
    assert verified[0]["year"] == 2025


def test_missing_fallback_config_is_safe(monkeypatch):
    monkeypatch.setattr(educational_content, "SOURCE_FALLBACKS_PATH", ROOT / "does-not-exist.yaml")
    assert educational_content.load_source_fallbacks() == {}
