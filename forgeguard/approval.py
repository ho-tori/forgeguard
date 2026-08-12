import hashlib
import json
import os
import sqlite3
import time
import uuid

from .models import ApprovalRequest


def action_digest(action):
    canonical = json.dumps(
        {"action": action.name, "arguments": action.arguments},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class ApprovalStore:
    def __init__(self, path, ttl_seconds=300, clock=None):
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.clock = clock or time.time
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS approvals ("
                "id TEXT PRIMARY KEY, digest TEXT NOT NULL, risk TEXT NOT NULL, status TEXT NOT NULL, "
                "created REAL NOT NULL, expires REAL NOT NULL, consumed REAL)"
            )

    def request(self, action, risk):
        now = self.clock()
        request = ApprovalRequest(str(uuid.uuid4()), action_digest(action), risk, "pending", now, now + self.ttl_seconds)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO approvals(id,digest,risk,status,created,expires) VALUES(?,?,?,?,?,?)",
                (request.id, request.action_digest, request.risk, request.status, request.created_at, request.expires_at),
            )
        return request

    def decide(self, approval_id, approved):
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status=? WHERE id=? AND status='pending'",
                ("approved" if approved else "rejected", approval_id),
            )
        return cursor.rowcount == 1

    def consume(self, approval_id, action):
        now = self.clock()
        digest = action_digest(action)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT digest,status,expires FROM approvals WHERE id=?", (approval_id,)
            ).fetchone()
            if row is None or row[0] != digest or row[1] != "approved" or row[2] < now:
                if row is not None and row[2] < now and row[1] in ("pending", "approved"):
                    connection.execute("UPDATE approvals SET status='expired' WHERE id=?", (approval_id,))
                return False
            cursor = connection.execute(
                "UPDATE approvals SET status='consumed', consumed=? WHERE id=? AND status='approved'",
                (now, approval_id),
            )
            return cursor.rowcount == 1

