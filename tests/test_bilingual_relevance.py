import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from editorial import filter_ai_relevance


def _item(title, summary="", category="ai", **extra):
    item = {
        "title": title,
        "summary": summary,
        "category": category,
        "content_type": "research",
        "source": "Test",
        "source_tier": 1,
    }
    item.update(extra)
    return item


def test_persian_ai_core_is_relevant():
    result = filter_ai_relevance([
        _item("پیشرفت تازه در هوش مصنوعی مولد", "این پژوهش درباره مدل زبانی بزرگ و یادگیری عمیق است.")
    ], ["AI"])
    assert len(result) == 1


def test_persian_ai_agents_are_relevant():
    result = filter_ai_relevance([
        _item("عامل‌های هوشمند و آینده خودکارسازی پژوهش", "سامانه‌های عامل‌محور برای مدل استدلالی و انجام پژوهش به کار گرفته می‌شوند.")
    ], ["AI"])
    assert len(result) == 1


def test_persian_quantum_without_ai_stays_rejected():
    result = filter_ai_relevance([
        _item("پیشرفت مهم در محاسبات کوانتومی", "این متن فقط درباره کیوبیت، تصحیح خطا و پردازنده کوانتومی است.", category="quantum")
    ], ["AI"])
    assert result == []


def test_persian_quantum_with_ai_is_relevant():
    result = filter_ai_relevance([
        _item("یادگیری ماشین کوانتومی برای مدل‌های هوش مصنوعی", "این مطالعه از محاسبات کوانتومی برای بهبود یادگیری ماشین استفاده می‌کند.", category="quantum")
    ], ["AI"])
    assert len(result) == 1


def test_generic_reasoning_alone_stays_rejected():
    result = filter_ai_relevance([
        _item("تحلیل استدلال انسانی", "این متن درباره منطق و فلسفه است و هیچ ارتباطی با هوش مصنوعی ندارد.", category="mind")
    ], ["AI"])
    assert result == []


def test_unrelated_persian_topic_stays_rejected():
    result = filter_ai_relevance([
        _item("روندهای جدید کشاورزی شهری", "این گزارش فقط درباره آبیاری، خاک و کشت گیاهان است.", category="health")
    ], ["AI"])
    assert result == []
