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



    def test_people_bootstrap_requires_30_unique_deliveries_and_matching_baseline(self):
        from scripts.production_closure_contract import people_bootstrap_state_complete

        names = [f"Person {index:02d}" for index in range(30)]
        state = {
            "status": "complete",
            "people_count": 30,
            "delivered_count": 30,
            "delivered_people": names,
            "baseline": {
                name: {
                    "title": f"{name} reports a relevant technology development",
                    "link": f"https://example.org/story-{index}",
                    "published": "2026-10-01 10:00",
                }
                for index, name in enumerate(names)
            },
        }
        self.assertTrue(people_bootstrap_state_complete(state))
        duplicate = {**state, "delivered_people": names[:-1] + [names[0]]}
        self.assertFalse(people_bootstrap_state_complete(duplicate))
        self.assertFalse(people_bootstrap_state_complete({**state, "status": "in_progress"}))
        missing_evidence = {
            **state,
            "baseline": {**state["baseline"], names[0]: {"title": "T", "link": "", "published": "2026-10-01"}},
        }
        self.assertFalse(people_bootstrap_state_complete(missing_evidence))

    def test_health_snapshot_must_be_at_least_as_new_as_latest_production_start(self):
        from scripts.production_closure_contract import health_snapshot_fresh

        state = {"updated_at": 200.0, "telemetry": {"updated_at": 200.0}}
        self.assertTrue(health_snapshot_fresh(state, "1970-01-01T00:03:19+00:00"))
        self.assertFalse(health_snapshot_fresh(state, "1970-01-01T00:03:21+00:00"))
        self.assertFalse(health_snapshot_fresh({}, "1970-01-01T00:03:19+00:00"))

if __name__ == "__main__":
    unittest.main()
