import unittest

from tools.build_golden_seed import REQUIRED_FIELDS, build_seed


class GoldenSeedTests(unittest.TestCase):
    def test_seed_is_annotation_ready_and_not_pretending_to_be_labeled(self):
        feedback = {
            "messages": {
                "1": {
                    "chat_id": -100,
                    "message_id": 1,
                    "source": "Source A",
                    "content_type": "interview",
                    "leader": "Sam Altman",
                    "title": "Interview",
                    "link": "https://example.com/1",
                    "posted_at": 10,
                },
                "2": {
                    "chat_id": -100,
                    "message_id": 2,
                    "source": "Source B",
                    "content_type": "news",
                    "title": "News",
                    "link": "https://example.com/2",
                    "posted_at": 20,
                },
            }
        }
        rows = build_seed(feedback, limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["case_id"], "hist-0001")
        self.assertIsNone(rows[0]["should_publish"])
        self.assertIsNone(rows[0]["importance_band"])
        self.assertEqual(rows[0]["leader_name"], "Sam Altman")
        for row in rows:
            self.assertEqual(set(REQUIRED_FIELDS), set(row))

    def test_duplicate_links_are_collapsed(self):
        feedback = {
            "messages": {
                "1": {"link": "https://example.com/x", "posted_at": 10, "title": "x"},
                "2": {"link": "https://example.com/x", "posted_at": 20, "title": "x duplicate"},
            }
        }
        rows = build_seed(feedback)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_items"][0]["title"], "x duplicate")


if __name__ == "__main__":
    unittest.main()
