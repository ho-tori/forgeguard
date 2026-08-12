import hashlib
import json
import os
import threading
import time

from .models import AuditVerification
from .memory import redact_secrets


REDACT_KEYS = {"api_key", "authorization", "token", "secret", "password", "content"}


def _redact(value, key=None):
    if key and key.lower() in REDACT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return redact_secrets(value)
    return value


def _canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AuditLog:
    def __init__(self, path, clock=None):
        self.path = path
        self.head_path = path + ".head"
        self.clock = clock or time.time
        self._lock = threading.RLock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent)

    def _head(self):
        if not os.path.exists(self.head_path):
            return {"seq": 0, "hash": "0" * 64}
        with open(self.head_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def append(self, session_id, event, payload):
        with self._lock:
            head = self._head()
            record = {
                "seq": head["seq"] + 1,
                "timestamp": self.clock(),
                "session_id": session_id,
                "event": event,
                "payload": _redact(payload),
                "previous_hash": head["hash"],
            }
            record["hash"] = hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()
            with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(_canonical(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary = self.head_path + ".%s.tmp" % threading.get_ident()
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump({"seq": record["seq"], "hash": record["hash"]}, handle, sort_keys=True)
            os.replace(temporary, self.head_path)
            return record

    def read_all(self):
        with self._lock:
            if not os.path.exists(self.path):
                return []
            with open(self.path, "r", encoding="utf-8") as handle:
                return [json.loads(line) for line in handle if line.strip()]

    def verify(self):
        with self._lock:
            previous = "0" * 64
            count = 0
            try:
                records = self.read_all()
                for expected_seq, record in enumerate(records, 1):
                    count += 1
                    claimed = record.get("hash")
                    unsigned = dict(record)
                    unsigned.pop("hash", None)
                    actual = hashlib.sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
                    if record.get("seq") != expected_seq or record.get("previous_hash") != previous or claimed != actual:
                        return AuditVerification(False, count, "hash_chain_mismatch")
                    previous = claimed
                head = self._head()
                if head != {"seq": count, "hash": previous}:
                    return AuditVerification(False, count, "head_mismatch_or_truncation")
                return AuditVerification(True, count)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                return AuditVerification(False, count, "invalid_audit_log: %s" % exc)
