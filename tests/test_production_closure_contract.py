import unittest

from scripts.production_closure_contract import (
    is_persisted_state_skip,
    posts_sent_counts,
    publish_evidence,
    selected_candidate_count,
)


class TestProductionClosureContract(unittest.TestCase):
    def test_post_budget_zero_candidates_can_pass_with_explicit_acceptance(self):
        log = """
[Production Selection] total=0
[Publication Summary Budget] input=0 output=0 normal_window=0 replacement_buffer=0
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 0/0
[Production Acceptance] PASS: selected=0, published_news=0
"""
        self.assertEqual(selected_candidate_count(log), 0)
        self.assertEqual(posts_sent_counts(log), (0, 0))
        self.assertTrue(publish_evidence(log))

    def test_output_news_budget_zero_is_authoritative_over_earlier_selection(self):
        log = """
[Selection Timing] candidates=8
[Publication Summary Budget] input=8 output_news=0 final_capacity=3 candidate_window=6
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 0/0
[Production Acceptance] PASS: selected=0, published_news=0
"""
        self.assertEqual(selected_candidate_count(log), 0)
        self.assertTrue(publish_evidence(log))

    def test_output_news_nonzero_blocks_zero_candidate_evidence(self):
        log = """
[Selection Timing] candidates=8
[Publication Summary Budget] input=8 output_news=2 final_capacity=3 candidate_window=6
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 0/2
[Production Acceptance] PASS: selected=2, published_news=0
"""
        self.assertEqual(selected_candidate_count(log), 2)
        self.assertFalse(publish_evidence(log))

    def test_downstream_rejection_is_not_zero_candidate_evidence(self):
        log = """
[Production Selection] total=1
[Publication Summary Budget] input=1 output=1 normal_window=1
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 tier0_quota_exempt=true education=not_due
Posts sent: 0/1
[Production Acceptance] PASS: fail-closed editorial rejection
"""
        self.assertEqual(selected_candidate_count(log), 1)
        self.assertFalse(publish_evidence(log))

    def test_confirmed_delivery_requires_telegram_publication_marker(self):
        log = """
[Publication Summary Budget] input=1 output=1
[Production Contract] normal_news=1 normal_max=3 tier0_news=0 education=not_due
Posts sent: 1/1
[Production Acceptance] PASS: selected=1, published_news=1
"""
        self.assertFalse(publish_evidence(log))
        self.assertTrue(publish_evidence(log + "\n[Telegram Published] message_id=12"))

    def test_confirmed_education_is_a_real_publication(self):
        log = """
[Production Selection] total=0
[Production Contract] normal_news=0 normal_max=3 tier0_news=0 education=confirmed
Posts sent: 0/0
[Production Acceptance] PASS: selected=0, published_news=0, education=confirmed
[Education Published] CONFIRMED lesson_slot=2026-10-13:morning run=734 telegram_delivery=successful
"""
        self.assertTrue(publish_evidence(log))

    def test_latest_runtime_selection_count_wins_without_budget_marker(self):
        log = """
[Selection Timing] candidates=8
[Production Selection] total=2
Posts sent: 1/2
[Telegram Published] message_id=13
[Production Acceptance] PASS: published_news=1
"""
        self.assertEqual(selected_candidate_count(log), 2)
        self.assertTrue(publish_evidence(log))

    def test_only_skipped_state_persistence_push_is_ignored(self):
        run = {"event": "push", "head_commit": {"message": "chore: persist production state [skip ci]"}}
        self.assertTrue(is_persisted_state_skip(run, {"conclusion": "skipped"}))
        self.assertFalse(is_persisted_state_skip(run, {"conclusion": "success"}))
        self.assertFalse(is_persisted_state_skip({**run, "event": "schedule"}, {"conclusion": "skipped"}))
        self.assertFalse(is_persisted_state_skip({"event": "push", "head_commit": {"message": "other"}}, {"conclusion": "skipped"}))


if __name__ == "__main__":
    unittest.main()
