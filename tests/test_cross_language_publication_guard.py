import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from semantic_publication_guard import cross_language_anchor_conflict, shared_anchor_count


def test_same_story_survives_persian_english_rewrite():
    english = "Coursera backs co-founder Andrew Ng’s new AI education firm with $100 million investment"
    persian = "سرمایه‌گذاری ۱۰۰ میلیون دلاری Coursera در شرکت آموزشی جدید Andrew Ng"
    assert shared_anchor_count(english, persian) >= 3
    assert cross_language_anchor_conflict(english, persian)


def test_persian_and_arabic_digits_match_ascii_digits():
    assert shared_anchor_count("$100 million", "۱۰۰ میلیون") == 1
    assert shared_anchor_count("100 million", "١٠٠ میلیون") == 1


def test_same_person_without_story_anchors_is_not_blocked():
    left = "Andrew Ng discusses AI education research"
    right = "Andrew Ng launches a healthcare AI research initiative"
    assert shared_anchor_count(left, right) < 3
    assert not cross_language_anchor_conflict(left, right)
