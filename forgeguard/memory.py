import json
import os
import re
import sqlite3
from datetime import datetime

from .models import Memory


class SecretDetected(ValueError):
    pass


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)authorization\s*:\s*(?:bearer|basic)\s+\S+"),
)


def contains_secret(text):
    return any(pattern.search(text or "") for pattern in SECRET_PATTERNS)


def redact_secrets(text):
    value = text or ""
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _tokens(text):
    return set(re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", (text or "").lower()))


class MemoryStore:
    def __init__(self, path):
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, kind TEXT, content TEXT, tags TEXT, created_at TEXT)"
        )
        self.connection.commit()

    def add(self, session_id, kind, content, tags=None):
        if contains_secret(content):
            raise SecretDetected("Memory looks like it contains a credential")
        if not content or len(content) > 4000:
            raise ValueError("Memory content must contain 1-4000 characters")
        tags = tags or []
        created = datetime.utcnow().isoformat() + "Z"
        cursor = self.connection.execute(
            "INSERT INTO memories(session_id,kind,content,tags,created_at) VALUES(?,?,?,?,?)",
            (session_id, kind, content, json.dumps(tags), created),
        )
        self.connection.commit()
        return cursor.lastrowid

    def search(self, query, limit=5):
        query_tokens = _tokens(query)
        rows = self.connection.execute(
            "SELECT id,session_id,kind,content,tags,created_at FROM memories ORDER BY id DESC LIMIT 200"
        ).fetchall()
        scored = []
        for row in rows:
            item_tokens = _tokens(row[3] + " " + " ".join(json.loads(row[4])))
            score = len(query_tokens & item_tokens)
            if score:
                scored.append((score, row[0], row))
        scored.sort(key=lambda item: (-item[0], -item[1]))
        return [Memory(row[0], row[1], row[2], row[3], json.loads(row[4]), row[5]) for _, _, row in scored[:limit]]

    def count(self):
        return self.connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def clear(self):
        self.connection.execute("DELETE FROM memories")
        self.connection.commit()

    def close(self):
        self.connection.close()
