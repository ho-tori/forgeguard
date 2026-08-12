import json
import os
import tempfile
import threading
import unittest

from forgeguard.audit import AuditLog


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "audit.jsonl")
        self.audit = AuditLog(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_chain_and_payload_redaction(self):
        self.audit.append(
            "s1",
            "credential_set",
            {"api_key": "sk-secret", "argv": ["tool", "Authorization: Bearer must-not-remain"], "configured": True},
        )
        self.audit.append("s1", "tool_result", {"message": "ok"})
        result = self.audit.verify()
        self.assertTrue(result.ok)
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertNotIn("sk-secret", handle.read())
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertNotIn("must-not-remain", handle.read())

    def test_tamper_and_truncation_are_detected(self):
        self.audit.append("s1", "one", {"value": 1})
        self.audit.append("s1", "two", {"value": 2})
        with open(self.path, "r", encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle]
        records[0]["payload"]["value"] = 99
        with open(self.path, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")
        self.assertFalse(self.audit.verify().ok)

        audit2 = AuditLog(os.path.join(self.temp.name, "second.jsonl"))
        audit2.append("s1", "one", {})
        audit2.append("s1", "two", {})
        with open(audit2.path, "r", encoding="utf-8") as handle:
            first = handle.readline()
        with open(audit2.path, "w", encoding="utf-8") as handle:
            handle.write(first)
        self.assertFalse(audit2.verify().ok)

    def test_concurrent_appends_preserve_one_chain(self):
        def append_batch(worker):
            for index in range(20):
                self.audit.append("s%s" % worker, "event", {"index": index})

        threads = [threading.Thread(target=append_batch, args=(worker,)) for worker in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        result = self.audit.verify()
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.records, 80)


if __name__ == "__main__":
    unittest.main()
