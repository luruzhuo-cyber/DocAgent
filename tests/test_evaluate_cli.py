import unittest, tempfile, os, json, sys, runpy
from pathlib import Path
from unittest.mock import patch
from docagent.config import Settings


class EvalTimingTests(unittest.TestCase):
    def test_live_timer_excludes_preflight_retrieval(self):
        script = Path(__file__).resolve().parents[1] / "scripts/evaluate.py"

        class Retrieval:
            def __init__(self, *args, **kwargs):
                pass

            def search(self, *args, **kwargs):
                return {
                    "hits": [{"id": "x", "document": "d", "section": "s", "text": "t"}]
                }

        class Engine:
            def __init__(self, *args):
                pass

            def events(self, *args):
                return iter(
                    [
                        {
                            "event": "done",
                            "data": {
                                "answer": "t[x]",
                                "guard": "citation-format-valid",
                                "steps": 1,
                            },
                        }
                    ]
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "eval").mkdir()
            (root / "eval/questions.jsonl").write_text(
                json.dumps(
                    {
                        "id": "Q1",
                        "split": "test",
                        "kind": "single",
                        "question": "q",
                        "expected_evidence": [{"document": "d", "section": "s"}],
                        "expected_phrases": ["t"],
                    }
                ),
                encoding="utf8",
            )
            previous = os.getcwd()
            try:
                os.chdir(root)
                with patch(
                    "docagent.config.load_settings",
                    return_value=Settings(llm_api_key="test-only"),
                ), patch("docagent.retrieval.Retriever", Retrieval), patch(
                    "docagent.engine.Engine", Engine
                ), patch(
                    "sys.argv", [str(script), "--live"]
                ), patch(
                    "time.perf_counter", side_effect=[100, 101, 200, 203]
                ):
                    runpy.run_path(str(script), run_name="__main__")
                report = json.loads(
                    (root / "reports/evaluation.json").read_text(encoding="utf8")
                )
                self.assertEqual(report["results"][0]["total_seconds"], 3)
            finally:
                os.chdir(previous)
