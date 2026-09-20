from production_entrypoint import normal_news_policy_allowed


def test_first_normal_rank_uses_absolute_quality_floor_not_existing_baseline():
    assert normal_news_policy_allowed(63.19, 73.19, 1)
    assert normal_news_policy_allowed(63.18, 73.19, 1)
    assert normal_news_policy_allowed(60.0, 73.19, 1)
    assert not normal_news_policy_allowed(54.99, 73.19, 1)


def test_first_normal_rank_requires_quality_floor_without_baseline():
    assert not normal_news_policy_allowed(1.0, None, 1)
    assert normal_news_policy_allowed(60.0, None, 1)



def test_mission_recovery_can_publish_without_normal_rank_when_quality_floor_passes():
    assert normal_news_policy_allowed(55.41, None, None, mission_recovery=True)
    assert not normal_news_policy_allowed(54.99, None, None, mission_recovery=True)


def test_mission_recovery_does_not_bypass_normal_rank_for_regular_candidates():
    assert not normal_news_policy_allowed(60.0, None, None, mission_recovery=False)
