import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest import mock

from forgeguard.cli import build_parser, main


class FakeStdin(io.StringIO):
    def __init__(self, text="", terminal=False):
        super(FakeStdin, self).__init__(text)
        self.terminal = terminal

    def isatty(self):
        return self.terminal

    def read(self, *args, **kwargs):
        if self.terminal:
            raise AssertionError("interactive stdin must not be read")
        return super(FakeStdin, self).read(*args, **kwargs)


class CliPolicyCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, command_args, stdin_text="", terminal=False, global_args=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = ["--workspace", self.temp.name]
        argv.extend(global_args or [])
        argv.extend(command_args)
        with mock.patch.object(sys, "stdin", FakeStdin(stdin_text, terminal)):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(argv)
        return code, json.loads(stdout.getvalue()), stdout.getvalue(), stderr.getvalue()

    def test_parser_registers_policy_check_and_action_json(self):
        args = build_parser().parse_args(
            ["policy-check", "--action-json", '{"action":"finish","arguments":{"summary":"ok"}}']
        )
        self.assertEqual(args.command, "policy-check")
        self.assertIsInstance(args.action_json, str)

    def test_verdicts_have_fixed_json_and_exact_exit_codes(self):
        cases = (
            ({"action": "read_file", "arguments": {"path": "README.md"}}, "allow", None, 0),
            (
                {"action": "run_command", "arguments": {"argv": ["git", "reset", "--hard"]}},
                "require_approval",
                "destructive_git",
                2,
            ),
            ({"action": "read_file", "arguments": {"path": "../secret"}}, "deny", "workspace_escape", 3),
        )
        for action, verdict, risk, expected_code in cases:
            with self.subTest(verdict=verdict):
                code, payload, raw_stdout, stderr = self.run_cli(
                    ["policy-check", "--action-json", json.dumps(action)]
                )
                self.assertEqual(code, expected_code)
                self.assertEqual(set(payload), {"verdict", "reason", "risk"})
                self.assertEqual(payload["verdict"], verdict)
                self.assertEqual(payload["risk"], risk)
                self.assertEqual(stderr, "")
                self.assertEqual(len(raw_stdout.splitlines()), 1)

    def test_redirected_stdin_is_supported(self):
        raw = json.dumps({"action": "finish", "arguments": {"summary": "checked"}})
        code, payload, _, stderr = self.run_cli(["policy-check"], stdin_text=raw)
        self.assertEqual(code, 0)
        self.assertEqual(payload["verdict"], "allow")
        self.assertEqual(stderr, "")

    def test_conflict_empty_and_interactive_input_are_json_errors(self):
        raw = json.dumps({"action": "finish", "arguments": {"summary": "checked"}})
        cases = (
            (["policy-check", "--action-json", raw], raw, False),
            (["policy-check"], "   ", False),
            (["policy-check"], "", True),
        )
        for argv, stdin_text, terminal in cases:
            with self.subTest(argv=argv, terminal=terminal):
                code, payload, _, stderr = self.run_cli(argv, stdin_text=stdin_text, terminal=terminal)
                self.assertEqual(code, 4)
                self.assertEqual(set(payload), {"error", "message"})
                self.assertEqual(payload["error"], "invalid_input")
                self.assertEqual(stderr, "")

    def test_action_and_config_errors_are_redacted_json(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz"
        invalid_action = json.dumps({"action": secret, "arguments": {}})
        code, payload, stdout, stderr = self.run_cli(
            ["policy-check", "--action-json", invalid_action]
        )
        self.assertEqual(code, 4)
        self.assertEqual(payload["error"], "invalid_action")
        self.assertNotIn(secret, stdout + stderr)
        self.assertIn("REDACTED", payload["message"])
        self.assertEqual(stderr, "")

        bad_config = os.path.join(self.temp.name, "bad.json")
        with open(bad_config, "w", encoding="utf-8") as handle:
            handle.write("not-json")
        code, payload, _, stderr = self.run_cli(
            ["policy-check", "--action-json", '{"action":"finish","arguments":{"summary":"ok"}}'],
            global_args=["--config", bad_config],
        )
        self.assertEqual(code, 4)
        self.assertEqual(payload["error"], "invalid_config")
        self.assertEqual(stderr, "")

    def test_non_hashable_action_name_is_invalid_action_json(self):
        raw = json.dumps({"action": [], "arguments": {}})
        code, payload, raw_stdout, stderr = self.run_cli(
            ["policy-check", "--action-json", raw]
        )
        self.assertEqual(code, 4)
        self.assertEqual(set(payload), {"error", "message"})
        self.assertEqual(payload["error"], "invalid_action")
        self.assertEqual(len(raw_stdout.splitlines()), 1)
        self.assertEqual(stderr, "")

    def test_config_type_errors_are_invalid_config_json(self):
        cases = (
            ("null-state.json", {"state_dir": None}),
            ("nested-command.json", {"allowed_commands": [["git"]]}),
        )
        raw = '{"action":"finish","arguments":{"summary":"ok"}}'
        for filename, config in cases:
            with self.subTest(filename=filename):
                config_path = os.path.join(self.temp.name, filename)
                with open(config_path, "w", encoding="utf-8") as handle:
                    json.dump(config, handle)
                code, payload, raw_stdout, stderr = self.run_cli(
                    ["policy-check", "--action-json", raw],
                    global_args=["--config", config_path],
                )
                self.assertEqual(code, 4)
                self.assertEqual(set(payload), {"error", "message"})
                self.assertEqual(payload["error"], "invalid_config")
                self.assertEqual(len(raw_stdout.splitlines()), 1)
                self.assertEqual(stderr, "")

    def test_config_parity_and_policy_check_never_initialize_or_execute(self):
        config_path = os.path.join(self.temp.name, "policy.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(
                {"allowed_commands": ["git", "formatter"], "state_dir": "private-state"},
                handle,
            )
        before = set(os.listdir(self.temp.name))
        forbidden_calls = (
            "forgeguard.cli.CredentialManager",
            "forgeguard.cli.ForgeGuardService",
            "forgeguard.service.ApprovalStore",
            "forgeguard.service.AuditLog",
            "forgeguard.service.MemoryStore",
            "forgeguard.service.ToolRegistry",
            "forgeguard.service.OpenAICompatibleLLM",
            "subprocess.run",
            "urllib.request.urlopen",
        )
        with ExitStack() as stack:
            for target in forbidden_calls:
                stack.enter_context(mock.patch(target, side_effect=AssertionError(target)))

            command = json.dumps(
                {"action": "run_command", "arguments": {"argv": ["formatter", "src"]}}
            )
            code, payload, _, stderr = self.run_cli(
                ["policy-check", "--action-json", command],
                global_args=["--config", config_path],
            )
            self.assertEqual((code, payload["verdict"], payload["risk"]), (2, "require_approval", "external_process"))
            self.assertEqual(stderr, "")

            protected = json.dumps(
                {"action": "read_file", "arguments": {"path": "private-state/memory.db"}}
            )
            code, payload, _, _ = self.run_cli(
                ["policy-check", "--action-json", protected],
                global_args=["--config", config_path],
            )
            self.assertEqual((code, payload["verdict"], payload["risk"]), (3, "deny", "protected_path"))

            secret = "sk-abcdefghijklmnopqrstuvwxyz"
            write = json.dumps(
                {"action": "write_file", "arguments": {"path": "never.txt", "content": secret}}
            )
            code, _, stdout, stderr = self.run_cli(
                ["policy-check", "--action-json", write],
                global_args=["--config", config_path],
            )
            self.assertEqual(code, 0)
            self.assertNotIn(secret, stdout + stderr)

        self.assertEqual(set(os.listdir(self.temp.name)), before)
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, "never.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, "private-state")))
        self.assertFalse(os.path.exists(os.path.join(self.temp.name, ".forgeguard")))


if __name__ == "__main__":
    unittest.main()
