import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_identity import classify_story


def test_muse_three_headlines_one_story():
    items = [
        {"title": "Zuckerberg introduces Personal Superintelligence and Muse"},
        {"title": "Introducing Muse by Meta; a personal AI agent with dedicated secure cloud computing"},
        {"title": "Zuckerberg launches Personal Superintelligence plan and Muse agent"},
    ]
    assert all(classify_story(items[i], items[0])[0] == "DUPLICATE" for i in (1, 2))


def test_tao_two_rewrites_one_story():
    a = {"title": "Theoretical warning by Terence Tao: AI may exhaust open mathematical problems"}
    b = {"title": "Terence Tao: AI threatens the future of open science and mathematical problems"}
    assert classify_story(b, a)[0] == "DUPLICATE"


def test_stanford_two_rewrites_one_story():
    a = {"title": "AI legal review finds millions live under discriminatory local laws - Stanford HAI"}
    b = {"title": "AI-based legal review: millions of people live under discriminatory local laws"}
    assert classify_story(b, a)[0] == "DUPLICATE"


def test_material_security_update_is_not_duplicate():
    a = {"title": "Meta introduces Muse personal AI agent"}
    b = {"title": "Security vulnerability discovered in Muse", "summary": "Researchers found a vulnerability in Muse and published mitigation details."}
    assert classify_story(b, a)[0] != "DUPLICATE"


def test_same_company_different_product_is_not_duplicate():
    a = {"title": "Meta introduces Muse"}
    b = {"title": "Meta announces new AR glasses"}
    assert classify_story(b, a)[0] != "DUPLICATE"
