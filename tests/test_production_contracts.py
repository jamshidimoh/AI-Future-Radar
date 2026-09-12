import unittest
from pathlib import Path


class ProductionContractTests(unittest.TestCase):
    def test_education_persistence_has_stable_publication_identity(self):
        source = (Path(__file__).resolve().parents[1] / "production_entrypoint.py").read_text(encoding="utf-8")
        self.assertIn('item["publication_identity"] = f"education:{education_id}"', source)
        self.assertIn('item["title"] = item.get("title") or f"Education lesson {education_id}"', source)


if __name__ == "__main__":
    unittest.main()
