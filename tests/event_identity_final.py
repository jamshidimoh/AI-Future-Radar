import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from event_identity import classify_story

def test_muse():
    a={"title":"Zuckerberg introduces Personal Superintelligence and Muse"}; b={"title":"Introducing Muse by Meta; a personal AI agent with dedicated secure cloud computing"}
    assert classify_story(b,a)[0]=="DUPLICATE"

def test_tao():
    a={"title":"Theoretical warning by Terence Tao: AI may exhaust open mathematical problems"}; b={"title":"Terence Tao: AI threatens the future of open science and mathematical problems"}
    assert classify_story(b,a)[0]=="DUPLICATE"

def test_stanford():
    a={"title":"AI legal review finds millions live under discriminatory local laws - Stanford HAI"}; b={"title":"AI-based legal review: millions of people live under discriminatory local laws"}
    assert classify_story(b,a)[0]=="DUPLICATE"

def test_update_not_duplicate():
    a={"title":"Meta introduces Muse personal AI agent"}; b={"title":"Security vulnerability discovered in Muse","summary":"Researchers found a vulnerability in Muse and published mitigation details."}
    assert classify_story(b,a)[0] != "DUPLICATE"
