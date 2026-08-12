import os
import sys
import tempfile
import unittest

from forgeguard.models import Action
from forgeguard.policy import PolicyEngine
from forgeguard.tools import ToolRegistry


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = ToolRegistry(
            self.temp.name,
            PolicyEngine(self.temp.name, allowed_commands=[os.path.basename(sys.executable), sys.executable]),
            feedback_checks={
                "pass": [sys.executable, "-c", "print('green')"],
                "fail": [sys.executable, "-c", "import sys; print('red'); sys.exit(3)"],
            },
            command_timeout=1,
            output_limit=1000,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_atomic_write_and_read(self):
        written = self.registry.execute(Action("write_file", {"path": "src/x.txt", "content": "hello"}))
        read = self.registry.execute(Action("read_file", {"path": "src/x.txt"}))
        self.assertTrue(written.ok)
        self.assertEqual(read.data["content"], "hello")

    def test_policy_is_applied_inside_dispatcher(self):
        result = self.registry.execute(Action("read_file", {"path": "../secret"}))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "policy_denied")

    def test_file_with_obvious_secret_is_not_returned_to_model(self):
        path = os.path.join(self.temp.name, "notes.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("api_key = sk-abcdefghijklmnopqrstuvwxyz")
        result = self.registry.execute(Action("read_file", {"path": "notes.txt"}))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "secret_detected")
        self.assertNotIn("sk-", repr(result.as_dict()))

    def test_secret_content_is_not_written_or_returned_by_command(self):
        write = self.registry.execute(
            Action("write_file", {"path": "leak.txt", "content": "api_key=sk-abcdefghijklmnopqrstuvwxyz"})
        )
        command = self.registry.execute(
            Action("run_command", {"argv": [sys.executable, "-c", "print('sk-abcdefghijklmnopqrstuvwxyz')"]}),
            approved=True,
        )
        self.assertFalse(write.ok)
        self.assertEqual(write.code, "secret_detected")
        self.assertTrue(command.ok)
        self.assertNotIn("sk-", repr(command.as_dict()))
        self.assertIn("REDACTED", command.data["stdout"])

    def test_feedback_uses_exit_code(self):
        passed = self.registry.execute(Action("run_feedback", {"check": "pass"}))
        failed = self.registry.execute(Action("run_feedback", {"check": "fail"}))
        self.assertTrue(passed.ok)
        self.assertFalse(failed.ok)
        self.assertEqual(failed.data["exit_code"], 3)
        self.assertIn("red", failed.data["stdout"])

    def test_command_timeout_is_structured(self):
        result = self.registry.execute(
            Action("run_command", {"argv": [sys.executable, "-c", "__import__('time').sleep(5)"]}),
            approved=True,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "command_timeout")

    def test_subprocess_environment_does_not_inherit_secrets(self):
        old = os.environ.get("FORGEGUARD_API_KEY")
        os.environ["FORGEGUARD_API_KEY"] = "sk-this-must-not-reach-tools"
        try:
            result = self.registry.execute(
                Action(
                    "run_command",
                    {"argv": [sys.executable, "-c", "print(__import__('os').environ.get('FORGEGUARD_API_KEY','clean'))"]},
                ),
                approved=True,
            )
        finally:
            if old is None:
                os.environ.pop("FORGEGUARD_API_KEY", None)
            else:
                os.environ["FORGEGUARD_API_KEY"] = old
        self.assertTrue(result.ok)
        self.assertEqual(result.data["stdout"].strip(), "clean")


if __name__ == "__main__":
    unittest.main()
