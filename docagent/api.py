"""本地 FastAPI 服务；SSE 在工作线程迭代，工具事件即时发送。"""

import json
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from docagent.config import load_settings
from docagent.retrieval import Retriever
from docagent.engine import Engine

app = FastAPI(title="DocAgent", version="1.0.0")
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = load_settings()
        _engine = Engine(settings, Retriever(settings))
    return _engine


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    session_id: str = Field(
        default="local", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )


@app.get("/", response_class=HTMLResponse)
def home():
    return (
        Path(__file__)
        .with_name("static")
        .joinpath("index.html")
        .read_text(encoding="utf-8")
    )


@app.get("/health")
def health():
    engine = get_engine()
    return {
        "status": "ok",
        "chunks": len(engine.retriever.chunks),
        "llm_configured": bool(engine.settings.llm_api_key),
        "retrieval_mode": engine.retriever.mode,
        "max_steps": engine.settings.max_steps,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    result = get_engine().run(req.message, req.session_id)
    if result["guard"] == "service-error":
        raise HTTPException(status_code=503, detail=result)
    return result


@app.post("/chat/stream")
def stream(req: ChatRequest):
    def generate():
        for event in get_engine().events(req.message, req.session_id):
            yield "event: " + event["event"] + "\ndata: " + json.dumps(
                event["data"], ensure_ascii=False
            ) + "\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
