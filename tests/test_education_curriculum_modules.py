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
    assert ids == list(range(31, 101))
    assert len(ids) == len(set(ids))


def test_advanced_core_has_prerequisites_sources_and_domain():
    lessons = _lessons()
    for lesson in lessons:
        assert lesson.get("domain")
        assert lesson.get("prerequisites")
        assert all(int(x) < int(lesson["id"]) for x in lesson["prerequisites"])
        assert len(lesson.get("sources") or []) >= 2
        assert len(lesson.get("a", {}).get("seed", "")) >= 20
        assert len(lesson.get("b", {}).get("seed", "")) >= 20


def test_new_advanced_lessons_have_learning_questions_and_practice():
    lessons = {int(x["id"]): x for x in _lessons()}
    for lesson_id in range(58, 101):
        lesson = lessons[lesson_id]
        assert lesson.get("core_question")
        assert lesson.get("practice")
        assert len(lesson["sources"]) >= 2
