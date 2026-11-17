from pathlib import Path

import yaml

from src.editorial_core import filter_ai_relevance
from src.protected_editorial_lane import _thematic_signal
from src.unified_editorial_selection import mission_area_from_content

ROOT = Path(__file__).resolve().parents[1]


def _yaml(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_philosophy_mind_and_science_subtopics_are_mission_classified():
    cases = (
        "The hard problem of consciousness in AI systems",
        "The mind-body problem and artificial intelligence",
        "Functionalism and computationalism in machine intelligence",
        "Embodied cognition and AI models",
        "Scientific realism and AI-generated hypotheses",
        "Falsifiability and epistemology of AI",
    )
    for title in cases:
        assert mission_area_from_content({"title": title}) == "mind_cognition", title


def test_philosophy_mind_and_science_items_need_an_actual_ai_bridge():
    candidates = [
        {
            "title": "The hard problem of consciousness",
            "summary": "A philosophical discussion of subjective experience and qualia.",
            "category": "mind",
            "source_tier": 1,
        },
        {
            "title": "Scientific realism and falsifiability",
            "summary": "A general philosophy-of-science discussion without AI or machine intelligence.",
            "category": "mind",
            "source_tier": 1,
        },
    ]
    assert filter_ai_relevance(candidates, ai_keywords=[]) == []


def test_ai_linked_philosophy_of_mind_and_science_survives_and_is_routed_to_mind_lane():
    candidates = [
        {
            "title": "The hard problem of consciousness in artificial intelligence",
            "summary": "Researchers examine whether artificial systems can have subjective experience.",
            "category": "mind",
            "content_type": "research",
            "source_tier": 1,
        },
        {
            "title": "Scientific realism and AI-generated hypotheses",
            "summary": "A philosophy-of-science analysis of knowledge claims produced by artificial intelligence systems.",
            "category": "mind",
            "content_type": "research",
            "source_tier": 1,
        },
    ]
    result = filter_ai_relevance(candidates, ai_keywords=[])
    assert len(result) == 2
    assert all(item["topic_family"] == "consciousness_cognition" for item in result)
    assert all(item["mission_area"] == "mind_cognition" for item in result)


def test_protected_mind_lane_recognizes_philosophy_of_science_subtopics():
    item = {
        "title": "Scientific realism and AI-generated hypotheses",
        "summary": "A philosophy-of-science analysis of AI-produced explanations.",
        "category": "mind",
    }
    assert _thematic_signal(item)


def test_google_news_subtopic_queries_are_ai_linked_discovery_only():
    queries = _yaml("config/radar_google_news_queries.yaml")["google_news_queries"]
    names = {
        "Hard Problem of Consciousness and AI",
        "Mind-Body Problem and Embodied Cognition in AI",
        "Theories of Mind and Machine Consciousness",
        "Free Will, Intentionality and AI Agency",
        "AI Epistemology and Epistemic Agency",
        "Scientific Realism and AI-Generated Hypotheses",
        "Scientific Method, Causality and AI",
    }
    selected = [item for item in queries if item.get("name") in names]
    assert {item["name"] for item in selected} == names
    assert all(item.get("category") == "mind" for item in selected)
    assert all(item.get("tier") == 1 for item in selected)
    assert all(item.get("content_type") == "research" for item in selected)
    assert all("artificial intelligence" in item["query"].casefold()
               or "ai " in item["query"].casefold()
               or " ai" in item["query"].casefold()
               or "machine intelligence" in item["query"].casefold()
               for item in selected)


def test_source_governance_and_existing_publication_limits_are_unchanged():
    source_policy = _yaml("config/mind_philosophy_sources.yaml")
    mission = _yaml("config/mission_policy.yaml")["mission"]
    assert source_policy["lane"]["bridge_required"] is True
    assert mission["mind_cognition_target"] == 1
    assert mission["max_posts"] == 8
