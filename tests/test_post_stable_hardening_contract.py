from unittest.mock import patch

import production_entrypoint as production


def test_feedback_bonus_is_nonzero_for_positive_profile():
    store = {
        "messages": {
            "1": {"source": "Example", "reaction_counts": {"❤️": 4}, "comment_count": 2},
            "2": {"source": "Example", "reaction_counts": {"🔥": 3}, "comment_count": 1},
        }
    }
    item = {"source": "Example"}
    assert production._feedback_bonus(store, item) > 0


def test_feedback_bonus_does_not_change_publication_policy_directly():
    baseline = 55.75
    assert production.normal_news_policy_allowed(55.75, baseline, 1)
    assert not production.normal_news_policy_allowed(55.74, baseline, 1)


def test_provider_exhaustion_fails_closed_at_llm_boundary():
    from llm_router_light import call_llm_with_fallback

    providers = [
        {"name": "p1", "kind": "test", "model": "m1"},
        {"name": "p2", "kind": "test", "model": "m2"},
    ]

    def fail(*args, **kwargs):
        raise RuntimeError("forced provider exhaustion")

    with patch("llm_router_light._call_provider", side_effect=fail):
        try:
            call_llm_with_fallback("test", "payload", providers=providers)
        except Exception as exc:
            assert "forced provider exhaustion" in str(exc)
        else:
            raise AssertionError("provider exhaustion must fail closed")


def test_acceptance_workflow_contract_remains_present():
    text = (production.ROOT / ".github" / "workflows" / "final-acceptance.yml").read_text(encoding="utf-8")
    assert "python -m pytest -q" in text
    assert "tests/test_final_production_acceptance.py" in text
    assert "tests/test_production_acceptance_contract.py" in text
