import unittest
from docagent.safety import calculate


class SafetyTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(calculate("(12+3)*2"), 30)

    def test_reject_code(self):
        with self.assertRaises(ValueError):
            calculate('__import__("os")')

    def test_limit(self):
        with self.assertRaises(ValueError):
            calculate("9**99999")
