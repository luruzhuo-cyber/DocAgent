import unittest
from scripts.score_reviews import score_reviews


class ReviewScores(unittest.TestCase):
    def test_subset(self):
        result = score_reviews(
            {"results": [{"id": "Q1"}, {"id": "Q2"}]},
            [{"id": "Q1", "correctness": 2, "citation_support": 1, "notes": "checked"}],
        )
        self.assertEqual(result["human_review"]["reviewed_count"], 1)
        self.assertEqual(result["human_review"]["fully_correct_rate"], 1)
        self.assertEqual(result["human_review"]["mean_citation_support"], 0.5)
        self.assertFalse(result["results"][1].get("manual_reviewed", False))

    def test_invalid(self):
        for reviews in (
            [{"id": "missing", "correctness": 2, "citation_support": 2}],
            [{"id": "Q1", "correctness": 3, "citation_support": 2}],
            [{"id": "Q1", "correctness": True, "citation_support": 2}],
            [{"id": "Q1", "correctness": 2, "citation_support": 2}] * 2,
        ):
            with self.assertRaises(ValueError):
                score_reviews({"results": [{"id": "Q1"}]}, reviews)
