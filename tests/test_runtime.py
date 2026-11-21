import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from langchain_core.messages import AIMessage, ToolMessage
from docagent.engine import Engine, ABSTAIN


def tool(name, args):
    return AIMessage(content="", tool_calls=[dict(name=name, args=args, id="t")])


class Model:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.seen = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.seen.append(list(messages))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


class Retriever:
    def search(self, query, top_k=5, rerank=False):
        return {
            "hits": [
                dict(
                    id="one",
                    document="guide",
                    section="intro",
                    text="first",
                    source="local",
                )
            ]
        }

    def read_section(self, document, section):
        return [
            dict(
                id="two",
                document=document,
                section=section,
                text="second",
                source="local",
            )
        ]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def make(self, responses, budget=1000):
        model = Model(responses)
        settings = SimpleNamespace(
            db_path=Path(self.temp.name) / "memory.db",
            context_budget=budget,
            max_steps=6,
        )
        return Engine(settings, Retriever(), model), model

    def test_multistep_evidence(self):
        engine, model = self.make(
            [
                tool("search_docs", {"query": "q"}),
                tool("read_section", {"document": "guide", "section": "intro"}),
                AIMessage(content="Answer [one][two]"),
            ]
        )
        out = engine.run("q", "a")
        self.assertEqual(out["answer"], "Answer [one][two]")
        self.assertEqual(out["steps"], 3)
        self.assertEqual({s["id"] for s in out["sources"]}, {"one", "two"})
        self.assertTrue(all(t["ok"] for t in out["trace"]))
        self.assertTrue(any(isinstance(m, ToolMessage) for m in model.seen[-1]))

    def test_six_decisions_refuse(self):
        engine, model = self.make(
            [tool("search_docs", {"query": "q"}) for _ in range(6)]
        )
        out = engine.run("q", "a")
        self.assertEqual(out["answer"], ABSTAIN)
        self.assertEqual(out["steps"], 6)
        self.assertEqual(len(model.seen), 6)

    def test_invalid_arguments_recover(self):
        engine, _ = self.make(
            [
                tool("search_docs", {"query": "q", "top_k": 99}),
                AIMessage(content="claim [one]"),
            ]
        )
        out = engine.run("q", "a")
        self.assertFalse(out["trace"][0]["ok"])
        self.assertEqual(out["sources"], [])
        self.assertEqual(out["answer"], ABSTAIN)

    def test_error_done_events(self):
        engine, _ = self.make([RuntimeError("private-detail")])
        events = list(engine.events("q", "a"))
        self.assertEqual([x["event"] for x in events], ["status", "error", "done"])
        self.assertEqual(events[-1]["data"]["guard"], "service-error")
        self.assertNotIn("private-detail", str(events))

    def test_session_isolation(self):
        engine, model = self.make([AIMessage(content="refuse")])
        engine.memory.append("private", "user", "secret-marker")
        engine.run("q", "public")
        self.assertNotIn("secret-marker", str(model.seen))
        self.assertEqual(len(engine.memory.history("private")), 1)

    def test_summary_cannot_authorize_citation(self):
        engine, model = self.make(
            [
                AIMessage(content="summary [old]"),
                AIMessage(content="claim [old]"),
                AIMessage(content=ABSTAIN),
            ],
            100,
        )
        for i in range(6):
            engine.memory.append(
                "a", "user" if i % 2 == 0 else "assistant", str(i) + "x" * 70
            )
        out = engine.run("followup", "a")
        self.assertEqual(out["answer"], ABSTAIN)
        self.assertIn("summary [old]", str(model.seen[-1]))
        with engine.memory.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM summaries WHERE session=?", ("a",)
                ).fetchone()[0],
                1,
            )

    def test_malicious_calc(self):
        target = Path(self.temp.name) / "executed"
        expression = "__import__('pathlib').Path(" + repr(str(target)) + ").touch()"
        engine, _ = self.make(
            [
                tool("calculate", {"expression": expression}),
                AIMessage(content="claim [calc-1]"),
            ]
        )
        out = engine.run("q", "a")
        self.assertFalse(target.exists())
        self.assertFalse(out["trace"][0]["ok"])
        self.assertEqual(out["answer"], ABSTAIN)

    def test_calculation_requires_retrieval(self):
        engine, _ = self.make(
            [tool("calculate", {"expression": "2+3"}), AIMessage(content="5 [calc-1]")]
        )
        out = engine.run("q", "a")
        self.assertFalse(out["trace"][0]["ok"])
        self.assertEqual(out["answer"], ABSTAIN)

    def test_calculation_after_retrieval_records_provenance(self):
        engine, _ = self.make(
            [
                tool("search_docs", {"query": "q"}),
                tool("calculate", {"expression": "2+3"}),
                AIMessage(content="5 [calc-2]"),
            ]
        )
        out = engine.run("q", "a")
        self.assertTrue(out["trace"][1]["ok"])
        self.assertEqual(out["answer"], "5 [calc-2]")
        calc = next(s for s in out["sources"] if s["id"] == "calc-2")
        self.assertEqual(calc["input_evidence"], ["one"])
        self.assertIn("5", calc["text"])

    def test_rerank_setting_is_forwarded(self):
        from unittest.mock import Mock

        engine, _ = self.make(
            [tool("search_docs", {"query": "q"}), AIMessage(content="answer [one]")]
        )
        engine.settings.use_rerank = True
        engine.retriever.search = Mock(wraps=engine.retriever.search)
        out = engine.run("q", "a")
        self.assertTrue(out["trace"][0]["ok"])
        engine.retriever.search.assert_called_once_with("q", top_k=5, rerank=True)
