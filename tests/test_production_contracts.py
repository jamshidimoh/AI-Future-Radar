import unittest
from unittest.mock import patch

import production_entrypoint


class ProductionContractTests(unittest.TestCase):
    def test_education_persistence_has_stable_publication_identity(self):
        item = {"content_type": "education", "education_id": 16, "title": "Lesson 16"}
        store = {"posts": []}
        meta = {"message_id": 123}

        with patch.object(production_entrypoint, "register_post") as register_post:
            production_entrypoint._register_successful_publication(store, meta, item)

        self.assertEqual(item["publication_identity"], "education:16")
        register_post.assert_called_once_with(store, meta, item)


if __name__ == "__main__":
    unittest.main()
