import unittest
from unittest.mock import patch

import main


class ProductionContractTests(unittest.TestCase):
    def test_education_persistence_has_stable_publication_identity(self):
        item = {"content_type": "education", "education_id": 16}
        seen_hashes = set()
        seen_signatures = set()
        source_history = []
        with patch("main.mark_as_seen") as mark_seen, patch("main.save_seen") as save_seen, patch("builtins.print") as printer:
            main._persist_item_success(item, seen_hashes, seen_signatures, source_history)
        self.assertEqual(item["publication_identity"], "education:16")
        mark_seen.assert_called_once_with(item, seen_hashes, seen_signatures, source_history)
        save_seen.assert_called_once_with(seen_hashes, seen_signatures, source_history)
        rendered = " ".join(str(call.args[0]) for call in printer.call_args_list if call.args)
        self.assertIn("education=education:16", rendered)


if __name__ == "__main__":
    unittest.main()
