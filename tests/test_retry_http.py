"""通过本机 OpenAI 兼容 HTTP 桩验证实际 SDK 重试，不连接外部服务。"""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from docagent.config import Settings
from docagent.engine import Engine


class RetryHTTPTests(unittest.TestCase):
    def run_case(self, status):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.server.calls += 1
                code = status if self.server.calls <= 2 or status == 400 else 200
                data = (
                    {
                        "error": {
                            "message": "simulated error",
                            "type": "test",
                            "code": "test",
                        }
                    }
                    if code != 200
                    else {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "created": 0,
                        "model": "test",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "ok"},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                )
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", "0")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.calls = 0
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                settings = Settings(
                    llm_api_key="local-test-only",
                    llm_base_url=f"http://127.0.0.1:{server.server_port}/v1",
                    llm_model="test",
                    db_path=str(Path(directory) / "memory.db"),
                    timeout=2,
                    retries=2,
                )
                model = Engine(settings, None)._model()
                if status == 400:
                    from openai import BadRequestError

                    with self.assertRaises(BadRequestError):
                        model.invoke("test")
                else:
                    self.assertEqual(model.invoke("test").content, "ok")
                return server.calls
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_transient_503_retries_twice(self):
        self.assertEqual(self.run_case(503), 3)

    def test_bad_request_never_retries(self):
        self.assertEqual(self.run_case(400), 1)
