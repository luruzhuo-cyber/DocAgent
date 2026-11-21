import unittest
from docagent.engine import verify_answer


class GuardTests(unittest.TestCase):
    def test_current_evidence_only(self):
        self.assertEqual(
            verify_answer("结论[old]", {"new"}), "资料不足，无法根据本轮检索证据回答。"
        )

    def test_refusal_cannot_bypass(self):
        self.assertEqual(
            verify_answer("杜撰。资料不足", set()),
            "资料不足，无法根据本轮检索证据回答。",
        )

    def test_valid(self):
        self.assertEqual(verify_answer("结论[new]", {"new"}), "结论[new]")
