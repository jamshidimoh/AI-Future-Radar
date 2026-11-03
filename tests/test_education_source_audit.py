from pathlib import Path

import tools.audit_education_sources as audit

ROOT = Path(__file__).resolve().parents[1]


def test_declared_year_alone_never_counts_as_current():
    result = audit.summarize([
        {
            "lesson_id": 1,
            "lesson_title": "Test",
            "url": "https://example.org/a",
            "host": "example.org",
            "organization": "example.org",
            "authority_tier": 4,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": None,
            "maintained_current": False,
            "current_2025_plus": False,
            "status": "ok",
        }
    ])
    assert "no_verified_current_source" in result["lessons"][0]["violations"]


def test_google_subdomains_are_not_treated_as_independent_sources():
    result = audit.summarize([
        {
            "lesson_id": 2,
            "lesson_title": "Test",
            "url": "https://developers.google.com/a",
            "host": "developers.google.com",
            "organization": "google",
            "authority_tier": 3,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": 2026,
            "maintained_current": False,
            "current_2025_plus": True,
            "status": "ok",
        },
        {
            "lesson_id": 2,
            "lesson_title": "Test",
            "url": "https://ai.google.dev/b",
            "host": "ai.google.dev",
            "organization": "google",
            "authority_tier": 3,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": 2026,
            "maintained_current": False,
            "current_2025_plus": True,
            "status": "ok",
        },
    ])
    assert "sources_not_independent_by_organization" in result["lessons"][0]["violations"]


def test_two_independent_current_sources_with_tier1_pass_core_quorum():
    result = audit.summarize([
        {
            "lesson_id": 1,
            "lesson_title": "Test",
            "url": "https://nist.gov/a",
            "host": "nist.gov",
            "organization": "nist",
            "authority_tier": 1,
            "reachable": True,
            "declared_year": 2025,
            "detected_year": 2025,
            "maintained_current": False,
            "current_2025_plus": True,
            "status": "ok",
        },
        {
            "lesson_id": 1,
            "lesson_title": "Test",
            "url": "https://example.edu/b",
            "host": "example.edu",
            "organization": "example.edu",
            "authority_tier": 2,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": 2026,
            "maintained_current": False,
            "current_2025_plus": True,
            "status": "ok",
        },
    ])
    assert result["lessons"][0]["violations"] == []
    assert result["lessons"][0]["warnings"] == []


# Keep the audit contract regression suite explicit and deterministic.



def test_audit_counts_verified_2026_sources_separately():
    result = audit.summarize([
        {
            "lesson_id": 3,
            "lesson_title": "Training and Inference",
            "url": "https://nist.gov/guide",
            "host": "nist.gov",
            "organization": "nist",
            "authority_tier": 1,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": 2026,
            "verified_source_year": 2026,
            "maintained_current": False,
            "current_2025_plus": True,
            "status": "dated_current",
        },
    ])
    assert result["policy"]["preferred_verified_year"] == 2026
    assert result["lessons"][0]["verified_2026_source_count"] == 1


def test_collect_includes_expansion_curriculum(monkeypatch, tmp_path):
    curriculum_path = tmp_path / "curriculum.yaml"
    modules_path = tmp_path / "modules.yaml"
    fallbacks_path = tmp_path / "fallbacks.yaml"
    emerging_path = tmp_path / "emerging.yaml"
    expansion_path = tmp_path / "expansion.yaml"
    monkeypatch.setattr(audit, "CURRICULUM", curriculum_path)
    monkeypatch.setattr(audit, "MODULES", modules_path)
    monkeypatch.setattr(audit, "FALLBACKS", fallbacks_path)
    monkeypatch.setattr(audit, "EMERGING", emerging_path)
    monkeypatch.setattr(audit, "EXPANSION", expansion_path)
    payloads = {
        curriculum_path: {"education": {"lessons": []}},
        modules_path: {"education_curriculum_modules": {"lessons": []}},
        fallbacks_path: {"education_source_fallbacks": {}},
        emerging_path: {"emerging_terminology": {"lessons": []}},
        expansion_path: {"education_curriculum_expansion": {"lessons": [
            {"id": 130, "title": "Agent Sandbox", "domain": "AI infrastructure", "sources": [
                {"name": "NIST", "url": "https://nist.gov/ai/agents", "year": 2026}
            ]}
        ]}},
    }
    monkeypatch.setattr(audit, "load_yaml", lambda path: payloads[path])
    monkeypatch.setattr(audit, "fetch_source", lambda url: (True, 2026, "ok"))
    rows = audit.collect()
    assert any(row["lesson_id"] == 130 for row in rows)
