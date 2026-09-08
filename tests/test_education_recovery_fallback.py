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


def test_deterministic_recovery_supports_lesson_112_current_source_override(monkeypatch):
    lesson = {
        "id": 112,
        "status": "emerging",
        "title": "Just-in-Time Context و Context Compaction",
        "a": {"term": "Just-in-Time Context", "fa": "زمینه در زمان نیاز", "seed": "راهبردی برای وارد کردن اطلاعات لازم در زمان مناسب."},
        "b": {"term": "Context Compaction", "fa": "فشرده‌سازی زمینه", "seed": "کاهش یا بازنمایی فشرده اطلاعات تاریخی یک اجرای طولانی برای حفظ اطلاعات مهم."},
        "relation": "یکی بر زمان بازیابی و دیگری بر فشرده‌سازی سابقه تمرکز دارد.",
        "sources": [{"name": "stale", "url": "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents", "year": 2025}],
    }
    monkeypatch.setattr(module, "_ORIGINAL_SOURCE_CANDIDATES", lambda _: lesson["sources"])
    candidates = module._source_candidates_with_current_overrides(lesson)
    urls = {item["url"] for item in candidates}
    assert "https://platform.claude.com/docs/en/build-with-claude/compaction" in urls
    assert "https://www.truefoundry.com/blog/jit-context-just-in-time-context-agents" in urls
    assert "https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents" not in urls


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
