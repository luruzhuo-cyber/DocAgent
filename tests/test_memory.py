import unittest, tempfile
from pathlib import Path
from docagent.memory import Memory


class MemoryTests(unittest.TestCase):
    def test_isolation_and_raw_history(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            m.append("a", "user", "secret")
            self.assertEqual(m.history("b"), [])
            self.assertEqual(m.history("a")[0]["content"], "secret")

    def test_compression_preserves_raw(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            for i in range(10):
                m.append("a", "user", str(i) * 100)
            summary, recent = m.context("a", 100, lambda text: "旧轮次结论")
            self.assertIn("旧轮次", summary)
            self.assertLess(len(recent), 10)
            self.assertEqual(len(m.history("a")), 10)
