import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from event_identity import classify_story

def test_known_duplicate_rewrites():
    cases = [
        ("Zuckerberg introduces Personal Superintelligence and Muse", "Introducing Muse by Meta; a personal AI agent with dedicated secure cloud computing"),
        ("Theoretical warning by Terence Tao: AI may exhaust open mathematical problems", "Terence Tao: AI threatens the future of open science and mathematical problems"),
        ("AI legal review finds millions live under discriminatory local laws - Stanford HAI", "AI-based legal review: millions of people live under discriminatory local laws"),
    ]
    for left, right in cases:
        assert classify_story({"title": right}, {"title": left})[0] == "DUPLICATE"

def test_material_update_survives():
    assert classify_story(
        {"title": "Security vulnerability discovered in Muse", "summary": "Researchers found a vulnerability in Muse and published mitigation details."},
        {"title": "Meta introduces Muse personal AI agent"},
    )[0] != "DUPLICATE"
