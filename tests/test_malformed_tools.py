import unittest, tempfile
from pathlib import Path
from types import SimpleNamespace
from langchain_core.messages import AIMessage
from docagent.engine import Engine, ABSTAIN
from test_runtime import Model, Retriever, tool


class MalformedToolTests(unittest.TestCase):
    def run_model(self, responses):
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(
                db_path=Path(directory) / "m.db",
                context_budget=1000,
                max_steps=6,
                use_rerank=False,
            )
            return Engine(settings, Retriever(), Model(responses)).run("query", "s")

    def invalid(self):
        return AIMessage(
            content="",
            invalid_tool_calls=[
                {
                    "name": "search_docs",
                    "args": "{",
                    "id": "bad",
                    "error": "invalid JSON",
                }
            ],
        )

    def test_invalid_json_is_repaired_within_budget(self):
        result = self.run_model(
            [
                self.invalid(),
                tool("search_docs", {"query": "q"}),
                AIMessage(content="answer[one]"),
            ]
        )
        self.assertEqual(result["answer"], "answer[one]")
        self.assertEqual(result["steps"], 3)

    def test_invalid_json_cannot_escape_step_limit(self):
        result = self.run_model([self.invalid() for _ in range(6)])
        self.assertEqual(result["answer"], ABSTAIN)
        self.assertEqual(result["steps"], 6)
