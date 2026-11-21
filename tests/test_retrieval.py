import unittest
from docagent.retrieval import chunk_text, Retriever


class RetrievalTests(unittest.TestCase):
    def test_stable_chunks(self):
        a = chunk_text(
            "# 查询参数\n查询参数用于分页。\n## 路径参数\n路径参数用于匹配。", "test.md"
        )
        self.assertEqual(
            a,
            chunk_text(
                "# 查询参数\n查询参数用于分页。\n## 路径参数\n路径参数用于匹配。",
                "test.md",
            ),
        )
        self.assertEqual(len(a), 2)

    def test_sparse(self):
        chunks = chunk_text("# 查询\n查询参数用于分页。\n# 状态\n状态码表示响应。", "x")
        r = Retriever(chunks, mode="bm25")
        self.assertEqual(r.search("分页")["hits"][0]["id"], chunks[0]["id"])

    def test_no_silent_dense_fallback(self):
        with self.assertRaises(ValueError):
            Retriever([], mode="invented")
