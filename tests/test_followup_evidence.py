import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from langchain_core.messages import AIMessage
from docagent.engine import Engine, ABSTAIN
from test_runtime import Model, Retriever, tool


class FollowupEvidenceTests(unittest.TestCase):
    def run_case(self, responses):
        with tempfile.TemporaryDirectory() as folder:
            s = SimpleNamespace(
                db_path=Path(folder) / "m.db",
                context_budget=1000,
                max_steps=6,
                use_rerank=False,
            )
            e = Engine(s, Retriever(), Model(responses))
            e.memory.append("s", "user", "earlier")
            e.memory.append("s", "assistant", "old answer [old]")
            return e.run("followup", "s")

    def test_followup_retrieves_current_evidence(self):
        out = self.run_case(
            [
                AIMessage(content="answer [old]"),
                tool("search_docs", {"query": "q"}),
                AIMessage(content="answer [one]"),
            ]
        )
        self.assertEqual(out["answer"], "answer [one]")
        self.assertEqual(out["steps"], 3)

    def test_repair_is_bounded_and_old_citation_stays_invalid(self):
        out = self.run_case(
            [AIMessage(content="answer [old]"), AIMessage(content="answer [old]")]
        )
        self.assertEqual(out["answer"], ABSTAIN)
        self.assertEqual(out["steps"], 2)

    def test_explicit_abstention_does_not_retry(self):
        out = self.run_case([AIMessage(content=ABSTAIN)])
        self.assertEqual(out["answer"], ABSTAIN)
        self.assertEqual(out["steps"], 1)
