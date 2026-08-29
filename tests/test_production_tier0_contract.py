from production_entrypoint import normal_news_policy_allowed


def test_normal_news_still_requires_normal_rank():
    assert not normal_news_policy_allowed(70.0, 55.75, None)
    assert normal_news_policy_allowed(70.0, 55.75, 1)
