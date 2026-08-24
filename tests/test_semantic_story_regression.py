import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from semantic_dedup import deduplicate_semantically, get_story_signature, _similarity


def test_rewritten_title_same_story_is_rejected():
    history = [
        "__semantic_story__:{\"context\":[\"andrew_ng\",\"ai\",\"agent\",\"launches\",\"new\",\"course\"],\"title\":[\"andrew_ng\",\"agent\",\"course\"]}"
    ]
    candidate = {
        "title": "Andrew Ng introduces a new course for AI agents",
        "summary": "Andrew Ng launches an AI agents course for developers.",
    }
    assert deduplicate_semantically([candidate], history, threshold=0.45) == []


def test_unrelated_story_is_not_rejected():
    history = [
        "__semantic_story__:{\"context\":[\"nvidia\",\"gpu\",\"datacenter\",\"chips\"],\"title\":[\"nvidia\",\"gpu\"]}"
    ]
    candidate = {
        "title": "MIT CSAIL researchers publish a new robotics study",
        "summary": "The study presents a new approach to robot learning.",
    }
    assert len(deduplicate_semantically([candidate], history, threshold=0.45)) == 1


def test_current_run_rewrite_is_clustered():
    items = [
        {"title": "NVIDIA unveils a new AI accelerator", "summary": "NVIDIA announced a new accelerator for AI workloads."},
        {"title": "New NVIDIA chip targets AI computing", "summary": "The company introduced an accelerator aimed at AI workloads."},
    ]
    result = deduplicate_semantically(items, [], threshold=0.45)
    assert len(result) == 1


def test_persian_listicle_rewrite_from_previous_run_is_rejected():
    previous = {
        "title": "معرفی ۱۰ خبرنامه برای پیشی گرفتن در حوزه AI",
        "summary": "فهرستی از ۱۰ خبرنامه برای پیگیری روندهای مهم هوش مصنوعی و فناوری.",
    }
    current = {
        "title": "معرفی ۱۰ خبرنامه برتر برای پیشتازی در AI",
        "summary": "۱۰ خبرنامه برتر برای دنبال کردن روندهای مهم هوش مصنوعی و فناوری.",
    }
    score = _similarity(get_story_signature(current), get_story_signature(previous))
    assert score >= 0.72
    assert deduplicate_semantically([current], [get_story_signature(previous)], threshold=0.45) == []


def test_different_listicle_count_is_not_auto_duplicate():
    previous = {"title": "معرفی ۱۰ خبرنامه برتر AI", "summary": "فهرست ۱۰ خبرنامه برای پیگیری هوش مصنوعی."}
    current = {"title": "معرفی ۲۰ خبرنامه برتر AI", "summary": "فهرست ۲۰ خبرنامه برای پیگیری هوش مصنوعی."}
    assert len(deduplicate_semantically([current], [get_story_signature(previous)], threshold=0.45)) == 1


def test_same_google_departure_event_from_different_sources_is_rejected():
    items = [
        {
            "title": "Google is expanding its AI empire — and losing the people who built it",
            "summary": "Google AI is losing several veterans as senior researchers and leaders leave the company.",
        },
        {
            "title": "Google AI exodus continues as four veterans leave; Demis Hassabis steps down as Google DeepMind leader",
            "summary": "Four veterans leave Google AI and Demis Hassabis steps down from the DeepMind leadership role.",
        },
    ]
    score = _similarity(get_story_signature(items[0]), get_story_signature(items[1]))
    assert score >= 0.70
    assert len(deduplicate_semantically(items, [], threshold=0.45)) == 1


def test_same_organization_different_event_is_not_rejected():
    items = [
        {
            "title": "Google AI veterans leave the company",
            "summary": "Several senior researchers depart Google AI.",
        },
        {
            "title": "Google launches a new AI model",
            "summary": "Google introduces a new model for developers.",
        },
    ]
    assert len(deduplicate_semantically(items, [], threshold=0.45)) == 2
