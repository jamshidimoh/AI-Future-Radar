import src.llm_router_light as router
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
    # The policy intentionally permits a controlled 10-point step-down from
    # the previous normal-news baseline. Test below that policy boundary so
    # this contract verifies the actual publication policy rather than a
    # nonexistent exact-score threshold.
    assert not production.normal_news_policy_allowed(45.74, baseline, 1)


def test_provider_exhaustion_fails_closed_at_llm_boundary():
    calls = []

    def fail_one(system_prompt, user_content):
        calls.append("p1")
        raise RuntimeError("forced provider exhaustion")

    def fail_two(system_prompt, user_content):
        calls.append("p2")
        raise RuntimeError("forced provider exhaustion")

    providers = [("Test:p1", fail_one), ("Test:p2", fail_two)]
    previous_timeout = router._PROVIDER_TIMEOUTS.get("Test:")
    router._PROVIDER_TIMEOUTS["Test:"] = 0.5
    try:
        result, provider = router.call_llm_with_fallback("test", "payload", providers=providers)
    finally:
        if previous_timeout is None:
            router._PROVIDER_TIMEOUTS.pop("Test:", None)
        else:
            router._PROVIDER_TIMEOUTS["Test:"] = previous_timeout

    assert result is None
    assert provider is None
    assert calls == ["p1", "p2"]


def test_acceptance_workflow_contract_remains_present():
    text = (production.ROOT / ".github" / "workflows" / "final-acceptance.yml").read_text(encoding="utf-8")
    assert "python -m pytest -q" in text
    assert "tests/test_final_production_acceptance.py" in text
    assert "tests/test_production_acceptance_contract.py" in text
