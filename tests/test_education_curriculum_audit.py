from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "EDUCATION_CURRICULUM_COVERAGE_AUDIT.md"


def _yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_curriculum_audit_exists_and_defines_all_required_domains():
    text = AUDIT.read_text(encoding="utf-8")
    required = [
        "AI fundamentals", "Machine learning", "Deep learning", "Generative AI",
        "LLM", "Multimodal AI", "Retrieval & RAG", "Agents & agentic systems",
        "Tool use & protocols", "Memory & context", "Evaluation & benchmarks",
        "Alignment & post-training", "Inference & optimization", "Data & data engineering",
        "AI security & robustness", "Safety & responsible AI", "Governance & policy",
        "AI infrastructure & compute", "Robotics & embodied AI", "AI for science & biomedicine",
        "Quantum AI", "Open models & ecosystems", "AI engineering & MLOps",
        "Human-AI interaction", "Emerging terminology", "Cognitive science",
    ]
    for domain in required:
        assert domain in text


def test_curriculum_has_complete_unique_sequence_1_to_130():
    base = _yaml(ROOT / "config" / "education_curriculum.yaml")["education"]["lessons"]
    modules = _yaml(ROOT / "config" / "education_curriculum_modules.yaml")["education_curriculum_modules"]["lessons"]
    emerging = _yaml(ROOT / "config" / "emerging_terminology.yaml")["emerging_terminology"]["lessons"]
    expansion = _yaml(ROOT / "config" / "education_curriculum_expansion.yaml")["education_curriculum_expansion"]["lessons"]
    lessons = base + modules + emerging + expansion
    ids = [int(x["id"]) for x in lessons]
    assert sorted(ids) == list(range(1, 131))
    assert len(ids) == len(set(ids))
    for lesson in lessons:
        assert len(lesson.get("sources") or []) >= 2
        assert lesson.get("a", {}).get("seed")
        assert lesson.get("b", {}).get("seed")
        assert lesson.get("module_id")
        assert lesson.get("module_title")
        assert lesson.get("core_question")
        assert lesson.get("learning_outcome")
        assert lesson.get("practice")
        assert all(int(p) < int(lesson["id"]) for p in lesson.get("prerequisites", []))


def test_curriculum_audit_preserves_source_governance_rules():
    text = AUDIT.read_text(encoding="utf-8")
    assert "منبع canonical/historical" in text
    assert "منبع جاری معتبر" in text
    assert "حداقل دو منبع مستقل معتبر" in text
    assert "برچسب وضعیت" in text
    assert "۱۳۰ درس" in text

def test_each_lesson_teaches_exactly_two_distinct_core_concepts():
    base = _yaml(ROOT / "config" / "education_curriculum.yaml")["education"]["lessons"]
    modules = _yaml(ROOT / "config" / "education_curriculum_modules.yaml")["education_curriculum_modules"]["lessons"]
    emerging = _yaml(ROOT / "config" / "emerging_terminology.yaml")["emerging_terminology"]["lessons"]
    expansion = _yaml(ROOT / "config" / "education_curriculum_expansion.yaml")["education_curriculum_expansion"]["lessons"]
    for lesson in base + modules + emerging + expansion:
        a, b = lesson["a"], lesson["b"]
        assert a["term"].strip().casefold() != b["term"].strip().casefold()
        assert a["fa"].strip() != b["fa"].strip()
        assert a["term"] in lesson["title"]
        assert b["term"] in lesson["title"]


def test_all_thirteen_modules_are_declared_and_used():
    base = _yaml(ROOT / "config" / "education_curriculum.yaml")["education"]
    modules = _yaml(ROOT / "config" / "education_curriculum_modules.yaml")["education_curriculum_modules"]
    emerging = _yaml(ROOT / "config" / "emerging_terminology.yaml")["emerging_terminology"]
    expansion = _yaml(ROOT / "config" / "education_curriculum_expansion.yaml")["education_curriculum_expansion"]
    declared = (base.get("modules") or []) + (modules.get("modules") or []) + (emerging.get("modules") or []) + (expansion.get("modules") or [])
    assert sorted(int(x["id"]) for x in declared) == list(range(1, 14))
    used = {int(x["module_id"]) for x in base["lessons"] + modules["lessons"] + emerging["lessons"] + expansion["lessons"]}
    assert used == set(range(1, 14))
