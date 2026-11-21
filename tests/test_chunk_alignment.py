import unittest
from docagent.retrieval import chunk_text, Retriever


class ChunkAlignment(unittest.TestCase):
    def test_fixed_body_without_heading_has_section(self):
        chunks = chunk_text("# Example\n" + "x" * 150, "d", strategy="fixed", size=40)
        fragment = chunks[1]
        self.assertNotIn("# Example", fragment["text"])
        self.assertIn("Example", fragment["sections"])
        self.assertIn(fragment, Retriever(chunks).read_section("d", "Example"))

    def test_identical_fixed_blocks_unique(self):
        chunks = chunk_text("a" * 160, "d", strategy="fixed", size=40)
        self.assertEqual(len({c["id"] for c in chunks}), len(chunks))

    def test_structural_sections(self):
        for c in chunk_text("# A\nx\n# B\ny", "d"):
            self.assertEqual(c["sections"], [c["section"]])
