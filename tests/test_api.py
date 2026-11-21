import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from docagent.api import app


class InjectedEngine:
    def __init__(self, error=False):
        self.error = error
        self.retriever = SimpleNamespace(chunks=[{}], mode="bm25")
        self.settings = SimpleNamespace(llm_api_key="", max_steps=6)

    def run(self, message, session_id):
        return dict(
            answer="unavailable" if self.error else message,
            guard="service-error" if self.error else "citation-format-valid",
            sources=[],
            session=session_id,
        )

    def events(self, message, session_id):
        yield dict(event="status", data={"message": "working"})
        if self.error:
            yield dict(event="error", data={"message": "unavailable"})
        else:
            yield dict(event="token", data={"text": message})
        yield dict(event="done", data=self.run(message, session_id))


class APITests(unittest.TestCase):
    def setUp(self):
        self.engine = InjectedEngine()
        self.patch = patch("docagent.api.get_engine", return_value=self.engine)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.client = TestClient(app)

    def test_home_and_health(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["chunks"], 1)
        self.assertNotIn("llm_api_key", health.json())

    def test_chat_passes_session(self):
        response = self.client.post(
            "/chat", json={"message": "question", "session_id": "session-a"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "question")
        self.assertEqual(response.json()["session"], "session-a")

    def test_stream_valid_events(self):
        response = self.client.post(
            "/chat/stream", json={"message": "question", "session_id": "a"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        frames = response.text.strip().split("\n\n")
        self.assertEqual(
            [f.splitlines()[0] for f in frames],
            ["event: status", "event: token", "event: done"],
        )
        self.assertEqual(
            json.loads(frames[-1].split("data: ", 1)[1])["answer"], "question"
        )

    def test_errors_http_and_stream(self):
        self.engine.error = True
        self.assertEqual(
            self.client.post("/chat", json={"message": "q"}).status_code, 503
        )
        response = self.client.post("/chat/stream", json={"message": "q"})
        frames = response.text.strip().split("\n\n")
        self.assertEqual(
            [f.splitlines()[0] for f in frames],
            ["event: status", "event: error", "event: done"],
        )
        self.assertEqual(
            json.loads(frames[-1].split("data: ", 1)[1])["guard"], "service-error"
        )

    def test_invalid_session_rejected(self):
        for endpoint in ("/chat", "/chat/stream"):
            for session in ("../other", "", "x" * 81):
                with self.subTest(endpoint=endpoint, session=session):
                    self.assertEqual(
                        self.client.post(
                            endpoint, json={"message": "q", "session_id": session}
                        ).status_code,
                        422,
                    )
