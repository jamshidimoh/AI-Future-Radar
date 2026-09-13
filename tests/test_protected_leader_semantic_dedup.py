import unittest

from src.story_identity import deduplicate_stories


class TestProtectedLeaderSemanticDedup(unittest.TestCase):
    def test_protected_leader_rewrites_are_deduplicated_within_run(self):
        items = [
            {
                "title": "Mark Zuckerberg announces Muse AI system",
                "summary": "Meta introduces Muse, a new AI system for content generation.",
                "source": "Source A",
                "content_type": "official",
                "leader": "Mark Zuckerberg",
                "protected_content": True,
                "published": "2026-09-13T06:00:00Z",
            },
            {
                "title": "Zuckerberg unveils Muse from Meta",
                "summary": "Meta presents its Muse AI system for content generation.",
                "source": "Source B",
                "content_type": "news",
                "leader": "Mark Zuckerberg",
                "protected_content": True,
                "published": "2026-09-13T05:55:00Z",
            },
        ]
        result = deduplicate_stories(items, history=[])
        self.assertEqual(len(result), 1)

    def test_protected_leader_material_update_is_kept(self):
        history = [
            {
                "title": "Mark Zuckerberg announces Muse AI system",
                "summary": "Meta introduces Muse, a new AI system.",
                "source": "Source A",
                "leader": "Mark Zuckerberg",
                "protected_content": True,
                "published": "2026-09-12T06:00:00Z",
            }
        ]
        candidate = {
            "title": "Mark Zuckerberg announces Muse AI system with newly revealed details",
            "summary": "Newly revealed evidence and details materially change the reported scope of Muse.",
            "source": "Source B",
            "leader": "Mark Zuckerberg",
            "protected_content": True,
            "published": "2026-09-13T06:00:00Z",
        }
        result = deduplicate_stories([candidate], history=history)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
