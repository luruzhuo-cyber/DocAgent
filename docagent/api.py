"""本地 FastAPI 服务；SSE 在工作线程迭代，工具事件即时发送。"""

import json
import threading
import uuid
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from docagent.documents import LIMIT, parse_document
from docagent.config import load_settings
from docagent.retrieval import Retriever
from docagent.engine import Engine

app = FastAPI(title="DocAgent", version="1.0.0")
_engine = None
_library_lock = threading.RLock()


def get_engine():
    global _engine
    with _library_lock:
        if _engine is None:
            settings = load_settings()
            _engine = Engine(settings, Retriever(settings))
        return _engine


def library_dir():
    return Path(load_settings().corpus_dir) / "uploads"


@app.get("/documents")
def documents():
    engine = get_engine()
    return {"documents": engine.retriever.list_documents()}


@app.put("/documents/upload")
async def upload(request: Request, filename: str):
    from starlette.concurrency import run_in_threadpool

    name = Path(filename.replace(chr(92), "/")).name
    if not name or len(name) > 140:
        raise HTTPException(400, "文件名无效")
    data = bytearray()
    async for piece in request.stream():
        if len(data) + len(piece) > LIMIT:
            raise HTTPException(413, "文件超过 20 MB")
        data.extend(piece)
    try:
        text = await run_in_threadpool(parse_document, name, bytes(data))
    except ImportError:
        raise HTTPException(503, "请安装 requirements.txt 中的文档解析依赖")
    except Exception as exc:
        detail = str(exc) if type(exc) is ValueError else "解析失败，请检查文件格式"
        raise HTTPException(422, detail)
    with _library_lock:
        folder = library_dir()
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " .-_" else "_" for c in name)
        path = folder / (uuid.uuid4().hex + "_" + safe_name + ".md")
        path.write_text(text, encoding="utf-8")
        invalidate_library()
    return {"id": path.name, "name": name, "status": "ready", "preview": text[:1200]}


def invalidate_library():
    global _engine
    _engine = None


@app.delete("/documents/{document_id}")
def delete_document(document_id: str):
    import re

    if not re.fullmatch(r"[a-f0-9]{32}_[^/\\]+\.md", document_id):
        raise HTTPException(404, "找不到可删除的上传文档")
    with _library_lock:
        path = library_dir() / document_id
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404, "找不到文档")
        path.unlink()
        invalidate_library()
    return {"status": "deleted"}


class ChatRequest(BaseModel):
    mode: Literal["documents", "general", "auto"] = "documents"
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


@app.get("/sessions")
def sessions():
    with get_engine().memory.connect() as db:
        rows = db.execute("""SELECT m.session, COUNT(*),
            (SELECT SUBSTR(u.content,1,48) FROM messages u
             WHERE u.session=m.session AND u.role='user' ORDER BY u.id LIMIT 1)
            FROM messages m GROUP BY m.session ORDER BY MAX(m.id) DESC""").fetchall()
    return {
        "sessions": [
            {"id": key, "messages": count, "title": title} for key, count, title in rows
        ]
    }


@app.get("/sessions/{session_id}")
def session_history(session_id: str):
    memory = get_engine().memory
    with memory.connect() as db:
        traces = db.execute(
            "SELECT payload FROM turn_traces WHERE session=? ORDER BY id", (session_id,)
        ).fetchall()
    return {
        "messages": memory.history(session_id),
        "traces": [json.loads(row[0]) for row in traces],
    }


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
    result = get_engine().run(
        req.message,
        req.session_id,
        **({"mode": req.mode} if req.mode != "documents" else {})
    )
    if result["guard"] == "service-error":
        raise HTTPException(status_code=503, detail=result)
    return result


@app.post("/chat/stream")
def stream(req: ChatRequest):
    def generate():
        for event in get_engine().events(
            req.message,
            req.session_id,
            **({"mode": req.mode} if req.mode != "documents" else {})
        ):
            yield "event: " + event["event"] + "\ndata: " + json.dumps(
                event["data"], ensure_ascii=False
            ) + "\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
