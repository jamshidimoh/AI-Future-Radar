from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "EDUCATION_CURRICULUM_COVERAGE_AUDIT.md"


def test_curriculum_audit_exists_and_defines_all_required_domains():
    text = AUDIT.read_text(encoding="utf-8")
    required = [
        "AI fundamentals",
        "Machine learning",
        "Deep learning",
        "Generative AI",
        "LLM",
        "Multimodal AI",
        "Retrieval & RAG",
        "Agents & agentic systems",
        "Tool use & protocols",
        "Memory & context",
        "Evaluation & benchmarks",
        "Alignment & post-training",
        "Inference & optimization",
        "Data & data engineering",
        "AI security & robustness",
        "Safety & responsible AI",
        "Governance & policy",
        "AI infrastructure & compute",
        "Robotics & embodied AI",
        "AI for science & biomedicine",
        "Quantum AI",
        "Open models & ecosystems",
        "AI engineering & MLOps",
        "Human-AI interaction",
        "Emerging terminology",
    ]
    for domain in required:
        assert domain in text


def test_curriculum_audit_preserves_source_governance_rules():
    text = AUDIT.read_text(encoding="utf-8")
    assert "منبع canonical/historical" in text
    assert "منبع جاری معتبر" in text
    assert "حداقل دو منبع مستقل معتبر" in text
    assert "برچسب وضعیت" in text
