import unittest

from production_entrypoint import EDUCATION_INTERVAL_RUNS, _education_is_due


class ProductionCadenceTests(unittest.TestCase):
    def test_education_interval_matches_four_hour_news_cadence(self):
        self.assertEqual(EDUCATION_INTERVAL_RUNS, 3)

    def test_education_due_on_first_run(self):
        self.assertTrue(_education_is_due(1, -3))

    def test_education_due_every_three_news_runs(self):
        self.assertFalse(_education_is_due(2, 1))
        self.assertFalse(_education_is_due(3, 1))
        self.assertTrue(_education_is_due(4, 1))
        self.assertFalse(_education_is_due(5, 4))
        self.assertFalse(_education_is_due(6, 4))
        self.assertTrue(_education_is_due(7, 4))


if __name__ == "__main__":
    unittest.main()
