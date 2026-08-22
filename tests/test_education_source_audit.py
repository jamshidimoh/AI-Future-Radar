from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_education_sources as audit


def test_declared_year_alone_never_counts_as_current():
    result = audit.summarize([
        {
            "lesson_id": 1,
            "lesson_title": "Test",
            "url": "https://example.org/a",
            "host": "example.org",
            "authority_tier": 4,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": None,
            "current_2025_plus": False,
            "status": "ok",
        }
    ])
    assert "no_verified_current_source" in result["lessons"][0]["violations"]


def test_two_independent_current_sources_with_tier1_pass_core_quorum():
    result = audit.summarize([
        {
            "lesson_id": 1,
            "lesson_title": "Test",
            "url": "https://nist.gov/a",
            "host": "nist.gov",
            "authority_tier": 1,
            "reachable": True,
            "declared_year": 2025,
            "detected_year": 2025,
            "current_2025_plus": True,
            "status": "ok",
        },
        {
            "lesson_id": 1,
            "lesson_title": "Test",
            "url": "https://example.edu/b",
            "host": "example.edu",
            "authority_tier": 2,
            "reachable": True,
            "declared_year": 2026,
            "detected_year": 2026,
            "current_2025_plus": True,
            "status": "ok",
        },
    ])
    assert result["lessons"][0]["violations"] == []
