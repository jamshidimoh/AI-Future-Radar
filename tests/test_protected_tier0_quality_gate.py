from pathlib import Path

from src.editorial_quality_policy import PROTECTED_SCORE_FLOOR, protected_score_allowed
from scripts.production_acceptance_guard import validate

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ENTRYPOINT = ROOT / "production_entrypoint.py"


def test_protected_tier0_uses_independent_absolute_quality_floor():
    assert PROTECTED_SCORE_FLOOR == 60.0
    assert protected_score_allowed(60.0)
    assert protected_score_allowed(75.0)
    assert not protected_score_allowed(59.99)
    assert not protected_score_allowed(28.16)
    assert not protected_score_allowed(25.23)


def test_production_entrypoint_enforces_protected_floor_before_publish():
    text = PRODUCTION_ENTRYPOINT.read_text(encoding="utf-8")
    assert "protected_score_allowed(score)" in text
    assert "tier0_score_policy_blocked:{score}<floor:{PROTECTED_SCORE_FLOOR}" in text
    assert "quality_floor={PROTECTED_SCORE_FLOOR}" in text


def test_tier0_quality_rejection_is_explicitly_accounted():
    log = """
[Production Selection] canonical_period_rank=true total=1
[Publication Contract] candidate rejected reason=tier0_score_policy_blocked:28.16<floor:60.0; continuing to next ranked candidate
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true tier0_quality_floor=60.0 education=not_due
Posts sent: 0/1
"""
    ok, reason = validate(log)
    assert ok
    assert "policy_rejections=1" in reason


def test_low_quality_tier0_publication_is_fail_closed():
    log = """
[Production Selection] total=1
[Tier0 Interview Priority] retained=1 quota_exempt=true
[Publication Policy] PUBLISH TIER0 interview/quote global_rank=1 tier0_rank=1 score=25.23 quota_exempt=true
Posts sent: 1/1
[Production Contract] normal_news=0 normal_max=3 tier0_news=1 tier0_quota_exempt=true tier0_quality_floor=60.0 education=not_due
"""
    ok, reason = validate(log)
    assert ok is False
    assert "low-quality Tier-0 publication observed" in reason
    assert "25.23" in reason
