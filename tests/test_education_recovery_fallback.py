import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "education_recovery.py"

spec = importlib.util.spec_from_file_location("education_recovery_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_deterministic_recovery_supports_the_actually_due_lesson(monkeypatch):
    lesson = {
        "id": 105,
        "status": "emerging",
        "title": "Harness Engineering و AI Agent Harness",
        "a": {"term": "Harness Engineering", "fa": "مهندسی هارنس عامل", "seed": "طراحی محیط، ابزارها، محدودیت‌ها، آزمون‌ها و بازخوردهایی که یک agent در آن‌ها کار می‌کند تا رفتار آن قابل کنترل‌تر و قابل ارزیابی‌تر شود."},
        "b": {"term": "Agent Harness", "fa": "هارنس عامل", "seed": "لایه اجرایی پیرامون یک AI agent که context، ابزار، مجوزها، مشاهده نتایج و کنترل اجرای آن را مدیریت می‌کند."},
        "relation": "Harness Engineering یک فعالیت طراحی است؛ Agent Harness سامانه یا لایه‌ای است که این طراحی را در اجرا پیاده می‌کند.",
    }
    sources = [
        {"name": "InfoQ", "url": "https://www.infoq.com/podcasts/mcp-vibe-coding-harness-engineering/", "year": 2026, "current_verified": True, "organization": "infoq.com", "authority_tier": 4, "authority_score": 90},
        {"name": "Anthropic", "url": "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents", "year": 2026, "current_verified": True, "organization": "anthropic", "authority_tier": 3, "authority_score": 90},
    ]
    monkeypatch.setattr(module.educational_content, "_next_lesson", lambda: (lesson, 105, 120))
    monkeypatch.setattr(module, "_collect_verified_current_sources", lambda _: sources)
    item = module._build_with_deterministic_recovery()
    assert item is not None
    assert item["education_id"] == 105
    assert item["education_track"] == "emerging"
    assert item["education_number"] == 5
    assert item["_provider"] == "deterministic curriculum fallback"
    assert len(item["education_sources"]) == 2


def test_recovery_fails_over_from_unavailable_candidate_to_current_candidates(monkeypatch):
    lesson = {
        "id": 113,
        "title": "Agentic Memory و Structured Memory",
        "domain": "AI agents",
        "a": {"term": "Agentic Memory", "fa": "حافظه عاملی", "seed": "memory for agents"},
        "b": {"term": "Structured Memory", "fa": "حافظه ساختاریافته", "seed": "structured metadata"},
    }
    candidates = [
        {"name": "unavailable-primary", "url": "https://primary.example/404", "year": 2026},
        {"name": "AWS", "url": "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-memory-metadata.html", "year": 2026, "authority": 99},
        {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/", "year": 2026, "authority": 96},
    ]

    def fake_fetch(url):
        if url.endswith("/404"):
            return "", None
        return "verified excerpt", 2026

    def fake_assess(**kwargs):
        return {
            "current": True,
            "status": "current",
            "year": kwargs.get("detected_year"),
            "organization": "aws.amazon.com" if "amazonaws" in kwargs["url"] else "microsoft.com",
            "authority_tier": 1,
            "authority_score": 99,
        }

    monkeypatch.setattr(module.educational_content, "_source_candidates", lambda _: candidates)
    monkeypatch.setattr(module.educational_content, "_fetch_reference", fake_fetch)
    monkeypatch.setattr(module, "assess_source", fake_assess)
    monkeypatch.setattr(module, "validate_current_sources", lambda sources: (len(sources) >= 2, sources[:2], "ok"))

    verified = module._collect_verified_current_sources(lesson)
    urls = [source["url"] for source in verified]
    assert "https://primary.example/404" not in urls
    assert len(verified) == 2
    assert urls[0].startswith("https://")


def test_recovery_has_no_lesson_specific_override_registry():
    assert not hasattr(module, "CURRENT_SOURCE_OVERRIDES")
    assert not hasattr(module, "_source_candidates_with_current_overrides")
    assert not hasattr(module, "_install_authoritative_source_override")


def test_deterministic_recovery_still_fails_closed_without_two_current_sources(monkeypatch):
    lesson = {
        "id": 105,
        "status": "emerging",
        "title": "Harness Engineering و AI Agent Harness",
        "a": {"term": "Harness Engineering", "fa": "مهندسی هارنس عامل", "seed": "تعریف پایه برای مفهوم اول است."},
        "b": {"term": "Agent Harness", "fa": "هارنس عامل", "seed": "تعریف پایه برای مفهوم دوم است."},
        "relation": "رابطه پایه دو مفهوم.",
    }
    monkeypatch.setattr(module.educational_content, "_next_lesson", lambda: (lesson, 105, 120))
    monkeypatch.setattr(module, "_collect_verified_current_sources", lambda _: [])
    assert module._build_with_deterministic_recovery() is None
