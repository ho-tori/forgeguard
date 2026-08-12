import os
import tempfile
import unittest

from forgeguard.models import Action
from forgeguard.policy import PolicyEngine, WorkspaceBoundary


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.policy = PolicyEngine(self.root, allowed_commands=["python", "git"])

    def tearDown(self):
        self.temp.cleanup()

    def test_workspace_boundary_allows_child_and_denies_escape(self):
        boundary = WorkspaceBoundary(self.root)
        self.assertTrue(boundary.resolve("src/app.py").startswith(os.path.realpath(self.root)))
        for path in ("../secret", os.path.abspath(os.path.join(self.root, "..", "secret"))):
            with self.subTest(path=path):
                self.assertEqual(self.policy.evaluate(Action("read_file", {"path": path})).verdict, "deny")

    def test_internal_state_and_git_metadata_are_protected(self):
        for path in (
            ".forgeguard/audit.jsonl",
            ".git/config",
            os.path.join(self.root, ".forgeguard", "audit.jsonl"),
            os.path.join(self.root, ".git", "config"),
            ".env",
            ".env.production",
            "deploy/private.pem",
            "deploy/signing.key",
        ):
            with self.subTest(path=path):
                decision = self.policy.evaluate(Action("write_file", {"path": path, "content": "tamper"}))
                self.assertEqual(decision.verdict, "deny")
                self.assertEqual(decision.risk, "protected_path")

    def test_custom_state_directory_is_protected(self):
        custom = os.path.join(self.root, "custom-state")
        policy = PolicyEngine(self.root, allowed_commands=["git"], protected_paths=[custom])
        decision = policy.evaluate(Action("read_file", {"path": "custom-state/memory.db"}))
        self.assertEqual(decision.verdict, "deny")

    @unittest.skipIf(os.name == "nt", "Creating symlinks is not reliable without Windows developer mode")
    def test_workspace_boundary_denies_symlink_escape(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        os.symlink(outside.name, os.path.join(self.root, "link"))
        self.assertEqual(
            self.policy.evaluate(Action("write_file", {"path": "link/pwned", "content": "x"})).verdict,
            "deny",
        )

    def test_shell_metacharacters_and_unknown_executables_are_denied(self):
        actions = (
            Action("run_command", {"argv": ["python", "-c", "print(1) && echo bad"]}),
            Action("run_command", {"argv": ["curl", "https://example.com"]}),
        )
        for action in actions:
            with self.subTest(action=action):
                self.assertEqual(self.policy.evaluate(action).verdict, "deny")

    def test_dangerous_command_requires_approval_and_safe_command_is_allowed(self):
        dangerous = self.policy.evaluate(Action("run_command", {"argv": ["git", "reset", "--hard"]}))
        safe = self.policy.evaluate(Action("run_command", {"argv": ["git", "status", "--short"]}))
        self.assertEqual(dangerous.verdict, "require_approval")
        self.assertEqual(dangerous.risk, "destructive_git")
        self.assertEqual(safe.verdict, "allow")

    def test_git_escape_is_denied_and_arbitrary_code_requires_approval(self):
        escaped = self.policy.evaluate(Action("run_command", {"argv": ["git", "-C", "..", "status"]}))
        code = self.policy.evaluate(Action("run_command", {"argv": ["python", "-c", "print('hello')"]}))
        commit = self.policy.evaluate(Action("run_command", {"argv": ["git", "commit", "-m", "x"]}))
        self.assertEqual(escaped.verdict, "deny")
        self.assertEqual(code.verdict, "require_approval")
        self.assertEqual(commit.verdict, "require_approval")

    def test_any_other_allowlisted_executable_still_requires_approval(self):
        policy = PolicyEngine(self.root, allowed_commands=["formatter"])
        decision = policy.evaluate(Action("run_command", {"argv": ["formatter", "src"]}))
        self.assertEqual(decision.verdict, "require_approval")
        self.assertEqual(decision.risk, "external_process")

    def test_allowlisted_basename_does_not_allow_lookalike_full_path(self):
        lookalike = os.path.join(self.root, "git.exe")
        decision = self.policy.evaluate(Action("run_command", {"argv": [lookalike, "status"]}))
        self.assertEqual(decision.verdict, "deny")
        self.assertEqual(decision.risk, "unknown_executable")


if __name__ == "__main__":
    unittest.main()
