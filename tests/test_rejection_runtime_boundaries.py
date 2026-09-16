from src.publication_orchestrator import _publication_reason_code


def test_publication_reason_maps_normal_score_floor():
    assert _publication_reason_code("normal_score_policy_blocked:54.99<floor:55.0") == "normal_score_floor"


def test_publication_reason_maps_protected_score_floor():
    assert _publication_reason_code("tier0_score_policy_blocked:54.99<floor:55.0") == "protected_score_floor"


def test_publication_reason_preserves_quota_and_rank_boundaries():
    assert _publication_reason_code("normal_quota_exhausted") == "publication_quota_exhausted"
    assert _publication_reason_code("normal_rank_outside_window:7") == "normal_rank_outside_window"


def test_publication_reason_falls_back_to_generic_policy_rejection():
    assert _publication_reason_code("some_future_policy_reason") == "publication_policy_rejection"
