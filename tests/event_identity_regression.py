import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_identity import classify_story, event_similarity


def test_muse_three_headlines_are_one_story():
    items = [
        {"title": "Zuckerberg introduces Personal Superintelligence and Muse", "published": "2026-09-09T05:00:00Z"},
        {"title": "Introducing Muse by Meta; a personal AI agent with dedicated secure cloud computing", "published": "2026-09-09T05:20:00Z"},
        {"title": "Zuckerberg launches Personal Superintelligence plan and Muse agent", "published": "2026-09-09T05:40:00Z"},
    ]
    assert event_similarity(items[0], items[1]) >= 0.78
    assert event_similarity(items[1], items[2]) >= 0.78
    assert classify_story(items[1], items[0])[0] == "DUPLICATE"
    assert classify_story(items[2], items[0])[0] == "DUPLICATE"


def test_terence_tao_rewrites_are_one_story():
    a = {"title": "Theoretical warning by Terence Tao: AI may exhaust open mathematical problems", "published": "2026-09-09T04:00:00Z"}
    b = {"title": "Terence Tao: AI threatens the future of open science and mathematical problems", "published": "2026-09-09T04:30:00Z"}
    assert classify_story(b, a)[0] == "DUPLICATE"


def test_stanford_hai_rewrites_are_one_story():
    a = {"title": "AI legal review finds millions live under discriminatory local laws", "published": "2026-09-09T03:00:00Z"}
    b = {"title": "AI-based legal review: millions of people live under discriminatory local laws", "published": "2026-09-09T03:15:00Z"}
    assert classify_story(b, a)[0] == "DUPLICATE"


def test_same_product_but_material_security_update_is_not_duplicate():
    original = {"title": "Meta introduces Muse personal AI agent", "summary": "Meta launches Muse as a personal AI agent."}
    update = {"title": "Security vulnerability discovered in Muse", "summary": "Researchers found a serious vulnerability in Muse and published mitigation details."}
    assert classify_story(update, original)[0] != "DUPLICATE"


def test_same_company_different_product_events_are_not_duplicate():
    a = {"title": "Meta introduces Muse", "summary": "Personal AI agent launch."}
    b = {"title": "Meta announces new AR glasses", "summary": "Meta announces a new augmented reality hardware product."}
    assert classify_story(b, a)[0] != "DUPLICATE"


def test_tao_different_later_event_is_not_duplicate():
    a = {"title": "Terence Tao warns about AI and open mathematical problems", "published": "2026-09-09T04:00:00Z"}
    b = {"title": "Terence Tao publishes new result on prime gaps", "published": "2026-12-20T04:00:00Z"}
    assert classify_story(b, a)[0] != "DUPLICATE"
