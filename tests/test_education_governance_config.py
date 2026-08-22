from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "education_governance.yaml"


def test_education_governance_policy_is_complete():
    data = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    policy = data["education_governance"]

    assert policy["priorities"] == [
        "scientific_authority",
        "current_validity",
        "topical_coverage",
    ]
    rules = policy["source_rules"]
    assert rules["dead_or_unreachable_url_is_never_verified"] is True
    assert rules["declared_year_alone_is_not_verification"] is True
    assert rules["established_foundational"]["minimum_sources"] >= 2
    assert rules["current_or_fast_moving"]["require_independent_sources"] is True
    assert rules["emerging_or_informal"]["require_status_label"] is True


def test_education_governance_covers_required_domains():
    data = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    domains = set(data["education_governance"]["curriculum_coverage"]["required_domains"])
    required = {
        "ai_fundamentals",
        "machine_learning",
        "deep_learning",
        "generative_ai",
        "llm",
        "multimodal_ai",
        "retrieval_and_rag",
        "agents_and_agentic_systems",
        "tool_use_and_protocols",
        "memory_and_context",
        "evaluation_and_benchmarks",
        "alignment_and_post_training",
        "inference_and_optimization",
        "data_and_data_engineering",
        "ai_security_and_robustness",
        "safety_and_responsible_ai",
        "governance_and_policy",
        "ai_infrastructure_and_compute",
        "robotics_and_embodied_ai",
        "ai_for_science_and_biomedicine",
        "quantum_ai",
        "open_models_and_ecosystems",
        "ai_engineering_and_mlops",
        "human_ai_interaction",
        "emerging_terminology",
    }
    assert required <= domains
