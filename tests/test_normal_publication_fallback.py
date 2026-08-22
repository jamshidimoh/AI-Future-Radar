from src.delivery_contract import DeliveryStatus, delivered, policy_blocked
import src.normal_publication_fallback as fallback


def _reset_state():
    fallback._NORMAL_DELIVERED = 0


def test_policy_block_remains_blocked():
    _reset_state()

    def policy(story):
        return policy_blocked("normal_score_policy_blocked:81.16<=81.06")

    fallback_policy, _ = fallback.wrap_policy(policy, lambda *_: None, rank_window=4)
    outcome = fallback_policy({"normal_period_rank": 2, "final_editorial_score": 81.16})
    assert outcome.status is DeliveryStatus.POLICY_BLOCKED
    assert outcome.message_id is None


def test_rank1_allowed_delivery_is_preserved():
    _reset_state()

    def policy(_story):
        return delivered({"message_id": 1234})

    fallback_policy, _ = fallback.wrap_policy(policy, lambda *_: None, rank_window=4)
    outcome = fallback_policy({"normal_period_rank": 1, "final_editorial_score": 85.0})
    assert outcome.status is DeliveryStatus.DELIVERED
    assert outcome.message_id == 1234


def test_non_score_policy_blocks_are_never_bypassed():
    _reset_state()
    fallback_policy, _ = fallback.wrap_policy(lambda _: policy_blocked("news_language_gate"), lambda *_: None)
    outcome = fallback_policy({"normal_period_rank": 2, "final_editorial_score": 97.59})
    assert outcome.status is DeliveryStatus.POLICY_BLOCKED
