from production_entrypoint import normal_news_policy_allowed


def test_first_normal_rank_respects_existing_baseline():
    assert normal_news_policy_allowed(63.19, 73.19, 1)
    assert not normal_news_policy_allowed(63.18, 73.19, 1)
    assert not normal_news_policy_allowed(61.95, 73.19, 1)


def test_first_normal_rank_is_allowed_without_baseline():
    assert normal_news_policy_allowed(1.0, None, 1)
