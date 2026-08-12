import json
import tempfile
import unittest

from forgeguard.models import PolicyDecision
from forgeguard.parser import ActionParseError
from forgeguard.policy import PolicyEngine
from forgeguard.policy_check import check_policy


class SecretReturningPolicy(object):
    def evaluate(self, action):
        return PolicyDecision(
            "deny",
            "token=abcdefghijklmnop",
            "api_key=qrstuvwxyzabcdef",
        )


class PolicyCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.policy = PolicyEngine(self.temp.name, allowed_commands=["git"])

    def tearDown(self):
        self.temp.cleanup()

    def test_returns_fixed_payload_for_all_three_verdicts(self):
        cases = (
            (
                {"action": "read_file", "arguments": {"path": "README.md"}},
                "allow",
                None,
            ),
            (
                {"action": "read_file", "arguments": {"path": "../secret.txt"}},
                "deny",
                "workspace_escape",
            ),
            (
                {"action": "run_command", "arguments": {"argv": ["git", "reset", "--hard"]}},
                "require_approval",
                "destructive_git",
            ),
        )
        for action, verdict, risk in cases:
            with self.subTest(verdict=verdict):
                result = check_policy(json.dumps(action), self.policy)
                self.assertEqual(set(result), {"verdict", "reason", "risk"})
                self.assertEqual(result["verdict"], verdict)
                self.assertEqual(result["risk"], risk)
                self.assertIsInstance(result["reason"], str)

    def test_accepts_every_existing_schema_and_preserves_strict_errors(self):
        actions = (
            {"action": "read_file", "arguments": {"path": "README.md"}},
            {"action": "write_file", "arguments": {"path": "out.txt", "content": "x"}},
            {"action": "run_command", "arguments": {"argv": ["git", "status", "--short"]}},
            {"action": "run_feedback", "arguments": {"check": "unit"}},
            {"action": "remember", "arguments": {"kind": "fact", "content": "x", "tags": []}},
            {"action": "finish", "arguments": {"summary": "done"}},
        )
        for action in actions:
            with self.subTest(action=action["action"]):
                self.assertIn(
                    check_policy(json.dumps(action), self.policy)["verdict"],
                    ("allow", "deny", "require_approval"),
                )

        invalid = '{"action":"browse","arguments":{}}'
        with self.assertRaises(ActionParseError):
            check_policy(invalid, self.policy)

    def test_redacts_reason_and_risk_without_echoing_action(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz"
        raw = json.dumps({"action": "finish", "arguments": {"summary": secret}})
        result = check_policy(raw, SecretReturningPolicy())
        rendered = repr(result)
        self.assertEqual(set(result), {"verdict", "reason", "risk"})
        self.assertNotIn(secret, rendered)
        self.assertNotIn("abcdefghijklmnop", rendered)
        self.assertNotIn("qrstuvwxyzabcdef", rendered)
        self.assertIn("REDACTED", rendered)


if __name__ == "__main__":
    unittest.main()
