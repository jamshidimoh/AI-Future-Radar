from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "config" / "education_curriculum_modules.yaml"


def _lessons():
    data = yaml.safe_load(MODULES.read_text(encoding="utf-8")) or {}
    return list(data.get("education_curriculum_modules", {}).get("lessons") or [])


def test_advanced_core_has_expected_lessons_and_unique_ids():
    lessons = _lessons()
    ids = [int(x["id"]) for x in lessons]
    assert ids == list(range(31, 58))
    assert len(ids) == len(set(ids))


def test_advanced_core_has_prerequisites_sources_and_domain():
    lessons = _lessons()
    for lesson in lessons:
        assert lesson.get("domain")
        assert lesson.get("prerequisites")
        assert len(lesson.get("sources") or []) >= 2
        assert len(lesson.get("a", {}).get("seed", "")) >= 20
        assert len(lesson.get("b", {}).get("seed", "")) >= 20


def test_advanced_core_covers_high_priority_gaps():
    domains = {str(x.get("domain")) for x in _lessons()}
    required = {
        "Inference & optimization",
        "Data & data engineering",
        "AI security & robustness",
        "AI for science & biomedicine",
        "Human-AI interaction",
        "Governance & policy",
        "Open models & ecosystems",
        "Robotics & embodied AI",
        "Quantum AI",
    }
    assert required <= domains


def test_three_pilot_lessons_cover_distinct_unfilled_topics():
    lessons = {int(x["id"]): x for x in _lessons()}
    assert set(lessons) >= {55, 56, 57}
    assert "Benchmark Contamination" in lessons[55]["title"]
    assert "Causal Inference" in lessons[56]["title"]
    assert "Scaling Laws" in lessons[57]["title"]
    for lesson_id in (55, 56, 57):
        lesson = lessons[lesson_id]
        assert len(lesson["sources"]) >= 2
        assert lesson["prerequisites"]
