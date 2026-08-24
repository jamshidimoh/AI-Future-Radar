import unittest

from src.editorial import classify_editorial_item, select_editorial
from main import _annotate_named_leader_interviews, _leader_source_authority, _split_protected


class ContentSelectionTests(unittest.TestCase):
    def test_leader_metadata_protects_interview_even_without_interview_keyword(self):
        item = {
            "title": "Sam Altman on the next phase of AI",
            "summary": "A long-form conversation about AI and education.",
            "watch_person": "Sam Altman",
            "leader": "Sam Altman",
            "is_leader_watch": True,
            "content_type": "interview",
            "category": "ai",
            "source_tier": 1,
            "editorial_score": 70,
        }
        result = classify_editorial_item(item, {"Sam Altman": 10})
        self.assertEqual(result["editorial_class"], "leader_interview")
        self.assertTrue(result["interview_signal"])

    def test_configured_leader_priority_is_preserved_for_protected_selection(self):
        items = [
            {
                "title": "Andrew Ng on the future of AI",
                "summary": "A long-form conversation about AI and education.",
                "leader": "Andrew Ng",
                "watch_person": "Andrew Ng",
                "content_type": "interview",
                "is_leader_watch": True,
                "published": "2026-08-15",
            },
            {
                "title": "Nick Bostrom on long-term AI risk",
                "summary": "A long-form conversation about superintelligence.",
                "leader": "Nick Bostrom",
                "watch_person": "Nick Bostrom",
                "content_type": "interview",
                "is_leader_watch": True,
                "published": "2026-08-15",
            },
        ]
        priorities = {"Andrew Ng": 10, "Nick Bostrom": 8}
        _annotate_named_leader_interviews(items, list(priorities), priorities)
        selected, _ = _split_protected(items, max_protected=1)
        self.assertEqual(selected[0]["leader"], "Andrew Ng")
        self.assertEqual(selected[0]["leader_priority"], 10)

    def test_protected_leader_prefers_authoritative_source_for_same_person(self):
        items = [
            {
                "title": "Dario Amodei interview on AI trust",
                "summary": "Dario Amodei discusses AI and public trust.",
                "leader": "Dario Amodei",
                "watch_person": "Dario Amodei",
                "content_type": "interview",
                "is_leader_watch": True,
                "leader_watch_protected": True,
                "leader_priority": 10,
                "source": "Bitcoin World",
                "source_tier": 3,
                "published": "2026-08-17",
            },
            {
                "title": "Anthropic leadership update involving Dario Amodei",
                "summary": "Reuters reports on an AI leadership development.",
                "leader": "Dario Amodei",
                "watch_person": "Dario Amodei",
                "content_type": "product_news",
                "is_leader_watch": True,
                "leader_watch_protected": True,
                "leader_priority": 10,
                "source": "Reuters",
                "source_tier": 2,
                "published": "2026-08-17",
            },
        ]
        selected, regular = _split_protected(items, max_protected=1)
        self.assertEqual(selected[0]["source"], "Reuters")
        self.assertEqual(selected[0]["leader_source_authority"], _leader_source_authority(selected[0]))
        self.assertEqual(regular[0]["source"], "Bitcoin World")

    def test_two_distinct_leaders_are_selected_before_news(self):
        items = [
            {"title": "Sam Altman future of AI", "summary": "conversation", "leader": "Sam Altman", "watch_person": "Sam Altman", "is_leader_watch": True, "content_type": "interview", "source": "A", "source_tier": 1, "editorial_score": 60},
            {"title": "Dario Amodei on AI", "summary": "conversation", "leader": "Dario Amodei", "watch_person": "Dario Amodei", "is_leader_watch": True, "content_type": "interview", "source": "B", "source_tier": 1, "editorial_score": 55},
            {"title": "New major AI model released", "summary": "launch", "content_type": "news", "source": "C", "source_tier": 1, "editorial_score": 95},
            {"title": "Research breakthrough in AI", "summary": "paper research findings", "content_type": "research", "source": "D", "source_tier": 1, "editorial_score": 80},
        ]
        enriched = []
        for item in items:
            data = dict(item)
            data.update(classify_editorial_item(data, {"Sam Altman": 10, "Dario Amodei": 10}))
            enriched.append(data)
        selected = select_editorial(enriched, max_posts=4, max_per_source=2, max_per_type=2, policy={"leader_interview_slots": 2})
        leader_names = [x.get("leader") for x in selected[:2]]
        self.assertEqual(set(leader_names), {"Sam Altman", "Dario Amodei"})
        self.assertEqual(len(selected), 4)

    def test_source_and_type_limits_are_enforced(self):
        items = []
        for i in range(8):
            items.append({
                "title": f"AI story {i}", "summary": "AI", "content_type": "news",
                "source": "same-source", "source_tier": 2, "editorial_score": 100 - i,
            })
        selected = select_editorial(items, max_posts=4, max_per_source=2, max_per_type=2, policy={"leader_interview_slots": 0})
        self.assertLessEqual(len(selected), 2)


if __name__ == "__main__":
    unittest.main()
