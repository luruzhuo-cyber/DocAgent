"""SQLite 保存原始记录与摘要；摘要仅供理解追问，不作为检索证据。"""

import sqlite3
import json
from contextlib import contextmanager
import threading
from pathlib import Path


class Memory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._locks = {}
        self._gate = threading.Lock()
        with self.connect() as c:
            c.executescript(
                "CREATE TABLE IF NOT EXISTS turn_traces(id INTEGER PRIMARY KEY, session TEXT, payload TEXT); CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,session TEXT,role TEXT,content TEXT); CREATE TABLE IF NOT EXISTS summaries(session TEXT PRIMARY KEY, upto INTEGER,content TEXT);"
            )

    def save_trace(self, session, trace):
        with self.connect() as db:
            db.execute(
                "INSERT INTO turn_traces(session,payload) VALUES (?,?)",
                (session, json.dumps(trace, ensure_ascii=False)),
            )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def lock(self, session):
        with self._gate:
            return self._locks.setdefault(session, threading.Lock())

    def append(self, session, role, content):
        with self.connect() as c:
            c.execute(
                "INSERT INTO messages(session,role,content) VALUES(?,?,?)",
                (session, role, content),
            )

    def history(self, session):
        with self.connect() as c:
            rows = c.execute(
                "SELECT role,content FROM messages WHERE session=? ORDER BY id",
                (session,),
            ).fetchall()
        return [dict(role=r, content=t) for r, t in rows]

    def context(self, session, budget, summarize):
        with self.connect() as c:
            old = c.execute(
                "SELECT upto,content FROM summaries WHERE session=?", (session,)
            ).fetchone()
            upto, summary = old if old else (0, "")
            rows = c.execute(
                "SELECT id,role,content FROM messages WHERE session=? AND id>? ORDER BY id",
                (session, upto),
            ).fetchall()
        # 用字符数近似预算；保留完整近期轮次，实际模型 token 统计由调用结果单独记录。
        budget = max(100, budget)
        size = len(summary) + sum(len(r[2]) for r in rows)
        if size > budget and len(rows) > 2:
            split = max(1, len(rows) - 2)
            older = rows[:split]
            rows = rows[split:]
            text = summary + "\n" + "\n".join(r[1] + ": " + r[2] for r in older)
            summary = summarize(text)[: budget // 2]
            with self.connect() as c:
                c.execute(
                    "INSERT OR REPLACE INTO summaries VALUES(?,?,?)",
                    (session, older[-1][0], summary),
                )
        result = []
        remaining = max(1, budget - len(summary))
        for _, role, content in reversed(rows):
            if len(content) > remaining:
                content = content[-remaining:]
            result.insert(0, dict(role=role, content=content))
            remaining -= len(content)
            if remaining <= 0:
                break
        return summary, result
