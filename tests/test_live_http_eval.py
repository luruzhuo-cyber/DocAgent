import unittest
from scripts.evaluate_live_http import aggregate


class LiveAggregation(unittest.TestCase):
    def test_failures_excluded_and_abstention_denominator(self):
        rows = [
            {
                "http_success": True,
                "kind": "single",
                "steps": 2,
                "seconds": 4,
                "refused": True,
            },
            {
                "http_success": True,
                "kind": "unanswerable",
                "steps": 4,
                "seconds": 8,
                "refused": True,
            },
            {
                "http_success": False,
                "kind": "unanswerable",
                "steps": 99,
                "seconds": 999,
                "refused": False,
            },
        ]
        m = aggregate(rows)
        self.assertEqual(m["mean_successful_steps"], 3)
        self.assertEqual(m["p95_successful_http_seconds"], 8)
        self.assertEqual(m["correct_unanswerable_abstention_rate"], 0.5)
        self.assertEqual(m["http_failures"], 1)

    def test_empty(self):
        self.assertIsNone(aggregate([])["correct_unanswerable_abstention_rate"])
        self.assertIsNone(aggregate([])["p95_successful_http_seconds"])
