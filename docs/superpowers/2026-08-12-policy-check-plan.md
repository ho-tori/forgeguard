# Policy Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `policy-check` CLI command that strictly parses one Action JSON, returns the existing policy verdict as JSON with stable exit codes, and never executes the Action or initializes runtime side effects.

**Architecture:** Add `forgeguard/policy_check.py` as a pure adapter over `parse_action()` and `PolicyEngine.evaluate()`. Keep `forgeguard/cli.py` as a thin boundary for mutually exclusive input selection, config loading, final redaction, JSON serialization, and exit-code mapping; update the deterministic demo and README without changing the existing Action schemas or policy rules.

**Tech Stack:** Python 3.7+ standard library, `argparse`, `json`, `unittest`, `unittest.mock`, existing ForgeGuard parser/policy/redaction modules, PowerShell verification commands.

## Global Constraints

- Python 3.7+; do not use `X | Y` type syntax, structural pattern matching, or APIs introduced after Python 3.7.
- No third-party runtime dependencies.
- Accept exactly one Action JSON from `--action-json` or redirected stdin; interactive stdin must never block.
- Accept exactly the six Action schemas already defined by `forgeguard.parser.SCHEMAS`.
- Output successful checks as exactly `verdict`, `reason`, and `risk`; preserve `risk=None` as JSON `null`.
- Exit codes are exactly `0=allow`, `2=require_approval`, `3=deny`, and `4=input/action/config error`.
- All policy-check errors are one JSON object on stdout; stderr remains empty.
- Reuse `redact_secrets()`; never echo the raw Action or maintain a second secret detector.
- Never construct or call `ForgeGuardService`, `CredentialManager`, `ApprovalStore`, `AuditLog`, `MemoryStore`, `ToolRegistry`, an LLM adapter, `subprocess`, or network code on the policy-check path.
- Never create `.forgeguard`, an approval, an audit event, memory, a file requested by the Action, or a command side effect.
- Do not change existing policy rules, Action schemas, WebUI/API behavior, or execution behavior.
- Every checkbox labeled `Micro-task` below is one executable task and must take 2–5 minutes. Numbered Task headings are review/commit groups, not execution-sized tasks; each group contains a complete RED→GREEN→REFACTOR cycle.
- Every implementation micro-task must explicitly follow `superpowers:test-driven-development`; production edits are forbidden until its paired RED command has run and the expected failure has been observed.
- Execute implementation only inside the `feat/policy-check` worktree created by `superpowers:using-git-worktrees`, never directly on `main`.

---

## File Responsibility Map

| File | Change | Single responsibility |
|---|---|---|
| `forgeguard/policy_check.py` | Create | Pure strict-parse → policy-evaluate → redacted result mapping. |
| `tests/test_policy_check.py` | Create | Pure service contract, all three verdicts, all six schemas, strict parse propagation, result redaction. |
| `forgeguard/cli.py` | Modify | Add CLI arguments, input selection, config/error adaptation, JSON output, and exit codes before runtime service construction. |
| `tests/test_cli_policy_check.py` | Create | CLI/stdin contract, exit codes, errors, config parity, secret leakage, and no-side-effect proof. |
| `forgeguard/demo.py` | Modify | Add one deterministic event proving a dangerous command is classified but not run. |
| `tests/test_demo.py` | Modify | Require the fifth policy-check event and its no-side-effect evidence. |
| `README.md` | Modify | Document both input forms, output shape, exit codes, and the non-execution guarantee. |
| `AGENT_LOG.md` | Modify in final task | Record actual RED/GREEN commands, observed summaries, reviews, subagents, decisions, and commit hashes. |

Do not modify `forgeguard/parser.py`, `forgeguard/policy.py`, `forgeguard/service.py`, `forgeguard/tools.py`, or any approval/audit/credential implementation. A needed change in one of those files is a design exception: stop and request human approval before proceeding.

## Exact Interfaces

Create this public function in `forgeguard/policy_check.py`:

```python
def check_policy(raw_action, policy):
    """Return {'verdict': str, 'reason': str, 'risk': Optional[str]}.

    Raise ActionParseError unchanged when raw_action fails the existing strict parser.
    Do not execute, persist, log, approve, or perform I/O.
    """
```

Add these private CLI interfaces in `forgeguard/cli.py`:

```python
POLICY_CHECK_EXIT_CODES = {"allow": 0, "require_approval": 2, "deny": 3}

def _read_policy_check_input(action_json, stdin):
    """Return the single non-empty raw JSON string or raise ValueError."""

def _emit_policy_check_error(code, error):
    """Print redacted {'error', 'message'} JSON to stdout and return 4."""

def _run_policy_check(args):
    """Load config, construct only PolicyEngine, print result JSON, return exit code."""
```

The argparse namespace for this subcommand must contain:

```python
args.command == "policy-check"
args.action_json is None or isinstance(args.action_json, str)
```

## Dependencies and Parallelism

```text
Task 1 pure service
├── Task 2 CLI contract and safety
└── Task 3 deterministic demo
       \
Task 2 ──┴──> Task 4 README
                 |
                 v
            Task 5 full regression and evidence
```

- Task 1 blocks Tasks 2 and 3 because both consume `check_policy(raw_action, policy)`.
- Tasks 2 and 3 are logically parallel after Task 1: they touch disjoint files except for consuming the new module.
- In Codex's shared workspace, run Tasks 2 and 3 sequentially. Parallelize only with separate worktrees/branches and integrate one complete reviewed commit at a time.
- Task 4 depends on Tasks 2 and 3 so its examples match real CLI and demo output.
- Task 5 depends on every prior task and is never parallel.
- After each numbered Task, run spec-compliance review first and code-quality review second. Fix every Critical or Important finding and repeat the scoped review before proceeding.

---

### Task 1: Pure Policy-Check Service Contract

**Files:**
- Create: `tests/test_policy_check.py`
- Create: `forgeguard/policy_check.py`

**Interfaces:**
- Consumes: `forgeguard.parser.parse_action(raw: str) -> Action`, `forgeguard.policy.PolicyEngine.evaluate(action) -> PolicyDecision`, `forgeguard.memory.redact_secrets(text: str) -> str`.
- Produces: `check_policy(raw_action, policy) -> dict` with exactly `verdict`, `reason`, `risk`; later Tasks 2 and 3 import it.

- [ ] **Micro-task 1 (2–5 min): Write the complete failing pure-service tests**

Create `tests/test_policy_check.py` with the complete content below:

```python
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
```

- [ ] **Micro-task 2 (2–5 min): Run RED and preserve the evidence**

Run:

```powershell
python -m unittest tests.test_policy_check -v
```

Expected RED: test discovery errors with `ModuleNotFoundError: No module named 'forgeguard.policy_check'`. Do not create the module before capturing this output.

- [ ] **Micro-task 3 (2–5 min): Write the minimal pure implementation**

Create `forgeguard/policy_check.py`:

```python
from .memory import redact_secrets
from .parser import parse_action


def _redact_optional(value):
    if value is None:
        return None
    return redact_secrets(value)


def check_policy(raw_action, policy):
    action = parse_action(raw_action)
    decision = policy.evaluate(action)
    return {
        "verdict": redact_secrets(decision.verdict),
        "reason": redact_secrets(decision.reason),
        "risk": _redact_optional(decision.risk),
    }
```

Do not import config, service, tools, approval, audit, credentials, subprocess, networking, or LLM modules here.

- [ ] **Micro-task 4 (2–5 min): Run GREEN for the new service**

Run:

```powershell
python -m unittest tests.test_policy_check -v
```

Expected GREEN: 3 tests pass with no skips or network access.

- [ ] **Micro-task 5 (2–5 min): REFACTOR verification against parser and policy regressions**

Review names and duplication, keep the module limited to the two functions above, then run:

```powershell
python -m unittest tests.test_policy_check tests.test_parser tests.test_policy -v
python -m compileall -q forgeguard/policy_check.py tests/test_policy_check.py
```

Expected REFACTOR result: all selected tests pass; compileall exits `0`; no production file other than `forgeguard/policy_check.py` changed.

- [ ] **Micro-task 6 (2–5 min): Commit the reviewed Task 1 unit**

```powershell
git add forgeguard/policy_check.py tests/test_policy_check.py
git commit -m "feat: add pure policy check service"
```

Before moving on, dispatch spec-compliance review and then code-quality review for this commit.

---

### Task 2: CLI Inputs, Exit Codes, Errors, Redaction, and No-Side-Effect Boundary

**Files:**
- Create: `tests/test_cli_policy_check.py`
- Modify: `forgeguard/cli.py`

**Interfaces:**
- Consumes: Task 1 `check_policy(raw_action, policy) -> dict`; `load_config(path, workspace) -> Config`; `PolicyEngine(workspace, allowed_commands, protected_paths)`.
- Produces: `forgeguard ... policy-check [--action-json JSON]`, private CLI helpers listed in “Exact Interfaces,” and exact exit-code mapping for Tasks 4 and 5.

- [ ] **Micro-task 1 (2–5 min): Create the CLI test harness and argument/exit-code tests**

Create `tests/test_cli_policy_check.py` with this complete content before editing `forgeguard/cli.py`:

```python
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
```

- [ ] **Micro-task 2 (2–5 min): Run the complete CLI RED suite**

Run:

```powershell
python -m unittest tests.test_cli_policy_check -v
```

Expected RED: argparse reports `policy-check` as an invalid choice and the test module fails/errors. Record the original output before editing `forgeguard/cli.py`.

- [ ] **Micro-task 3 (2–5 min): Register the CLI and add exact boundary helpers**

Modify imports at the top of `forgeguard/cli.py`:

```python
from .memory import redact_secrets
from .parser import ActionParseError
from .policy import PolicyEngine
from .policy_check import check_policy
```

In `build_parser()`, before the credential parser, add:

```python
    policy_check = commands.add_parser("policy-check", help="Check policy without executing an Action")
    policy_check.add_argument("--action-json", help="Strict Action JSON; reads redirected stdin when omitted")
```

Before `main()`, add exactly these helpers:

```python
POLICY_CHECK_EXIT_CODES = {"allow": 0, "require_approval": 2, "deny": 3}


def _read_policy_check_input(action_json, stdin):
    try:
        terminal = bool(getattr(stdin, "isatty", lambda: False)())
    except OSError:
        terminal = False
    redirected = "" if terminal else stdin.read()
    option_provided = action_json is not None
    stdin_provided = bool(redirected.strip())
    if option_provided and stdin_provided:
        raise ValueError("Provide Action JSON using either --action-json or stdin, not both")
    raw_action = action_json if option_provided else redirected
    if not isinstance(raw_action, str) or not raw_action.strip():
        raise ValueError("Action JSON must be provided using --action-json or redirected stdin")
    return raw_action


def _emit_policy_check_error(code, error):
    payload = {
        "error": redact_secrets(code),
        "message": redact_secrets(str(error)),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 4


def _run_policy_check(args):
    try:
        raw_action = _read_policy_check_input(args.action_json, sys.stdin)
    except (OSError, ValueError) as exc:
        return _emit_policy_check_error("invalid_input", exc)
    try:
        config = load_config(args.config, workspace=args.workspace)
    except ConfigError as exc:
        return _emit_policy_check_error("invalid_config", exc)
    policy = PolicyEngine(
        config.workspace,
        config.allowed_commands,
        protected_paths=[config.state_dir],
    )
    try:
        payload = check_policy(raw_action, policy)
    except ActionParseError as exc:
        return _emit_policy_check_error("invalid_action", exc)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return POLICY_CHECK_EXIT_CODES[payload["verdict"]]
```

- [ ] **Micro-task 4 (2–5 min): Route policy-check before credential/service construction**

In `main()`, immediately after the existing `demo` branch and before `credentials = CredentialManager()`, insert:

```python
        if args.command == "policy-check":
            return _run_policy_check(args)
```

Do not instantiate `ForgeGuardService` and close it for policy-check. Do not reuse the outer text/stderr exception handler for policy-check.

- [ ] **Micro-task 5 (2–5 min): Run GREEN for all CLI, secret, config, and side-effect cases**

Run:

```powershell
python -m unittest tests.test_cli_policy_check -v
```

Expected GREEN: 6 tests pass; stderr assertions are empty; the patched forbidden constructors/calls are untouched; no file or state directory is created.

- [ ] **Micro-task 6 (2–5 min): REFACTOR verification for CLI regressions and Python 3.7 syntax**

Keep helpers private and preserve the existing behavior for `run`, `serve`, credentials, audit, memory, and demo. Then run:

```powershell
python -m unittest tests.test_cli_policy_check tests.test_config tests.test_credentials tests.test_web -v
python -m compileall -q forgeguard/cli.py tests/test_cli_policy_check.py
git diff --check -- forgeguard/cli.py tests/test_cli_policy_check.py
```

Expected REFACTOR result: all selected tests pass with only existing platform skips; compileall and diff check exit `0`.

- [ ] **Micro-task 7 (2–5 min): Commit the reviewed Task 2 unit**

```powershell
git add forgeguard/cli.py tests/test_cli_policy_check.py
git commit -m "feat: add non-executing policy-check CLI"
```

Before moving on, dispatch spec-compliance review and then code-quality review. Review must explicitly examine service/credential construction order, stdout/stderr behavior, secret leakage, and Python 3.7 compatibility.

---

### Task 3: Deterministic Mechanism Demo

**Files:**
- Modify: `tests/test_demo.py`
- Modify: `forgeguard/demo.py`

**Interfaces:**
- Consumes: Task 1 `check_policy(raw_action, policy) -> dict` and existing `_reply(action, **arguments) -> str`.
- Produces: fifth demo event `5_policy_check` with `verdict`, `risk`, and `side_effect_free`; Task 4 documents it.

- [ ] **Micro-task 1 (2–5 min): Extend the demo test first**

In `tests/test_demo.py`, replace the event-name and final assertions in `test_mechanism_demo_is_deterministic` with:

```python
        self.assertEqual([event["demo"] for event in events], [
            "1_guardrail",
            "2_approval_binding",
            "3_feedback_loop",
            "4_audit",
            "5_policy_check",
        ])
        self.assertEqual(events[0]["state"], "awaiting_approval")
        self.assertTrue(events[1]["swap_blocked"])
        self.assertTrue(events[1]["replay_blocked"])
        self.assertTrue(events[2]["next_turn_saw_failure"])
        self.assertEqual(events[2]["final_content"], "fixed")
        self.assertEqual(events[4]["verdict"], "require_approval")
        self.assertEqual(events[4]["risk"], "arbitrary_code")
        self.assertTrue(events[4]["side_effect_free"])
```

- [ ] **Micro-task 2 (2–5 min): Run demo RED**

Run:

```powershell
python -m unittest tests.test_demo.DemoTests.test_mechanism_demo_is_deterministic -v
```

Expected RED: the event list contains only the existing four events, so the exact-list assertion fails before production demo code changes.

- [ ] **Micro-task 3 (2–5 min): Add the minimum non-executing demo event**

Add this import to `forgeguard/demo.py`:

```python
from .policy_check import check_policy
```

Immediately after emitting `4_audit`, before `memory.close()`, add:

```python
        marker_name = "policy-check-marker.txt"
        marker_path = os.path.join(workspace, marker_name)
        checked = check_policy(
            _reply(
                "run_command",
                argv=[
                    executable,
                    "-c",
                    "open(%r, 'w').write('executed')" % marker_name,
                ],
            ),
            policy,
        )
        side_effect_free = not os.path.exists(marker_path)
        _emit(
            stream,
            "5_policy_check",
            {
                "verdict": checked["verdict"],
                "risk": checked["risk"],
                "side_effect_free": side_effect_free,
            },
        )
```

Extend the final boolean expression with:

```python
            and checked["verdict"] == "require_approval"
            and checked["risk"] == "arbitrary_code"
            and side_effect_free
```

This argv would create a marker if executed; the demo proves `check_policy()` only classifies it.

- [ ] **Micro-task 4 (2–5 min): Run demo GREEN**

Run:

```powershell
python -m unittest tests.test_demo.DemoTests.test_mechanism_demo_is_deterministic -v
python -m forgeguard demo
```

Expected GREEN: the test passes; the command emits five JSON lines; `5_policy_check` reports `require_approval`, `arbitrary_code`, and `side_effect_free: true`; process exit is `0`.

- [ ] **Micro-task 5 (2–5 min): REFACTOR verification for deterministic behavior**

Run twice and compare exact output:

```powershell
$first = python -m forgeguard demo
$second = python -m forgeguard demo
if (($first -join "`n") -ne ($second -join "`n")) { throw "demo output is not deterministic" }
python -m unittest tests.test_demo tests.test_policy_check -v
git diff --check -- forgeguard/demo.py tests/test_demo.py
```

Expected REFACTOR result: identical output across both runs, selected tests pass, diff check exits `0`.

- [ ] **Micro-task 6 (2–5 min): Commit the reviewed Task 3 unit**

```powershell
git add forgeguard/demo.py tests/test_demo.py
git commit -m "demo: prove policy-check never executes actions"
```

Before moving on, dispatch spec-compliance review and then code-quality review.

---

### Task 4: README Contract and Usage Examples

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 2 CLI syntax/output/exit codes and Task 3 `5_policy_check` behavior.
- Produces: user-facing contract used during Task 5 verification.

- [ ] **Micro-task 1 (2–5 min): Run the README RED contract check before editing**

Run:

```powershell
$text = Get-Content -LiteralPath 'README.md' -Raw
$required = @(
  '## 只判断策略，不执行动作',
  'policy-check --action-json',
  '0=allow',
  '2=require_approval',
  '3=deny',
  '4=输入、Action 解析或配置错误'
)
$missing = @($required | Where-Object { -not $text.Contains($_) })
if ($missing.Count -ne 0) { throw ('README missing: ' + ($missing -join ', ')) }
```

Expected RED: PowerShell throws with all or some required policy-check strings missing.

- [ ] **Micro-task 2 (2–5 min): Add exact usage and safety documentation**

Insert this section after “快速体验” and before “安装” in `README.md`:

````markdown
## 只判断策略，不执行动作

`policy-check` 严格解析一个 Action JSON，并只返回现有 `PolicyEngine` 的治理判断。它不会执行文件写入、命令或反馈检查，不会创建或消费 approval，也不会初始化审计、记忆、凭据、LLM 或网络客户端。

通过参数传入：

```powershell
python -m forgeguard --workspace . policy-check --action-json '{"action":"run_command","arguments":{"argv":["git","status","--short"]}}'
```

或通过重定向 stdin 传入：

```powershell
'{"action":"read_file","arguments":{"path":"README.md"}}' | python -m forgeguard --workspace . policy-check
```

成功解析的 stdout 固定包含 `verdict`、`reason` 和 `risk`：

```json
{"reason": "Constrained git status is read-only", "risk": null, "verdict": "allow"}
```

退出码：`0=allow`、`2=require_approval`、`3=deny`、`4=输入、Action 解析或配置错误`。错误也只在 stdout 输出 JSON，stderr 为空。命令可读取 `--config` 中的工作区、状态目录和命令白名单设置，但不需要 API key、LLM 或网络。

确定性机制演示的 `5_policy_check` 事件使用一个若执行就会创建文件的 Python Action，并证明结果为 `require_approval` 且文件未创建：

```powershell
python -m forgeguard demo
```
````

- [ ] **Micro-task 3 (2–5 min): Run README GREEN checks and both documented commands**

Run:

```powershell
$text = Get-Content -LiteralPath 'README.md' -Raw
$required = @(
  '## 只判断策略，不执行动作',
  'policy-check --action-json',
  '0=allow',
  '2=require_approval',
  '3=deny',
  '4=输入、Action 解析或配置错误',
  '不会创建或消费 approval',
  '不需要 API key、LLM 或网络'
)
$missing = @($required | Where-Object { -not $text.Contains($_) })
if ($missing.Count -ne 0) { throw ('README missing: ' + ($missing -join ', ')) }
python -m forgeguard --workspace . policy-check --action-json '{"action":"run_command","arguments":{"argv":["git","status","--short"]}}'
if ($LASTEXITCODE -ne 0) { throw "documented --action-json example failed" }
'{"action":"read_file","arguments":{"path":"README.md"}}' | python -m forgeguard --workspace . policy-check
if ($LASTEXITCODE -ne 0) { throw "documented stdin example failed" }
```

Expected GREEN: required-string check succeeds; both documented commands emit one JSON object with `verdict=allow` and exit `0`.

- [ ] **Micro-task 4 (2–5 min): REFACTOR documentation verification**

Confirm every README claim has a matching automated assertion in `tests/test_cli_policy_check.py` or `tests/test_demo.py`, then run:

```powershell
python -m unittest tests.test_cli_policy_check tests.test_demo -v
git diff --check -- README.md
```

Expected REFACTOR result: selected tests pass and README has no whitespace errors.

- [ ] **Micro-task 5 (2–5 min): Commit the reviewed Task 4 unit**

```powershell
git add README.md
git commit -m "docs: document policy-check contract"
```

Before moving on, dispatch spec-compliance review and then code-quality review.

---

### Task 5: Full Regression, Security Scan, and Evidence Record

**Files:**
- Modify: `AGENT_LOG.md`
- Verify only: all files changed in Tasks 1–4

**Interfaces:**
- Consumes: all prior task commits and their review results.
- Produces: fresh verification evidence for completion/review; no feature behavior.

- [ ] **Micro-task 1 (2–5 min): Run the complete policy-check specialty suite**

```powershell
python -m unittest tests.test_policy_check tests.test_cli_policy_check tests.test_demo -v
```

Expected: 10 tests pass (3 pure-service + 6 CLI + 1 demo), no failures, no network, and no real credential access.

- [ ] **Micro-task 2 (2–5 min): Run the full repository regression**

```powershell
python -m unittest discover -s tests -v
```

Expected: 50 tests run, no failures; the existing POSIX-permission and Windows-symlink tests may remain skipped on Windows. Treat any new skip as a failure requiring investigation.

- [ ] **Micro-task 3 (2–5 min): Run demo, compile, and whitespace verification**

```powershell
python -m forgeguard demo
if ($LASTEXITCODE -ne 0) { throw "mechanism demo failed" }
python -m compileall -q forgeguard tests
if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
git diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed" }
```

Expected: five deterministic JSON demo events, compileall exit `0`, and no diff whitespace errors.

- [ ] **Micro-task 4 (2–5 min): Run credential and example-marker scans with explicit fixture allowlists**

```powershell
$credentialHits = @(git grep -n -I -E 'sk-[A-Za-z0-9_-]{16,}' -- .)
$unexpectedCredentials = @($credentialHits | Where-Object {
  $_ -notmatch '^(tests/test_(credentials|memory|tools|policy_check|cli_policy_check)\.py|docs/superpowers/2026-08-12-policy-check-plan\.md):'
})
if ($unexpectedCredentials.Count -ne 0) {
  $unexpectedCredentials
  throw "unexpected credential-like value outside explicit test/plan fixtures"
}

$exampleHits = @(git grep -n -I -E 'YOUR_[A-Z0-9_]+' -- . ':(exclude)docs/superpowers/2026-08-12-policy-check-plan.md' ':(exclude)AGENT_LOG.md')
$unexpectedExamples = @($exampleHits | Where-Object {
  $_ -notmatch '^README\.md:.*YOUR_PROVIDER_KEY'
})
if ($unexpectedExamples.Count -ne 0) {
  $unexpectedExamples
  throw "unexpected example marker"
}
```

Expected: credential-like values occur only in named deterministic test/plan fixtures; this plan file and `AGENT_LOG.md` are excluded because they are evidence/self-reference documents that carry the scan command itself rather than product/example surfaces. README and every other tracked file remain scanned, so the only remaining `YOUR_...` example is README's documented `YOUR_PROVIDER_KEY`.

- [ ] **Micro-task 5 (2–5 min): Record only observed evidence in AGENT_LOG.md**

Append a dated `policy-check` section to `AGENT_LOG.md` containing:

- the exact worktree path and baseline result;
- each Task's actual subagent identity;
- each RED command and the observed failure/error sentence;
- each GREEN/REFACTOR command and observed test counts;
- spec-compliance and code-quality review findings and dispositions;
- actual commit hashes from Tasks 1–4;
- human decisions, including the approved input/exit-code/schema/config/output choices;
- the exact final verification results from Micro-tasks 1–4.

Do not invent timestamps, agents, output, hashes, reviews, or CI/PR evidence. If a command did not run, record that it did not run and do not claim completion.

- [ ] **Micro-task 6 (2–5 min): Verify the evidence-only change and commit it**

```powershell
git diff --check -- AGENT_LOG.md
git add AGENT_LOG.md
git commit -m "chore: record policy-check verification evidence"
```

- [ ] **Micro-task 7 (2–5 min): Run fresh post-commit completion verification**

Use `superpowers:verification-before-completion`, then run on the committed tree:

```powershell
python -m unittest tests.test_policy_check tests.test_cli_policy_check tests.test_demo -v
python -m unittest discover -s tests -v
python -m forgeguard demo
python -m compileall -q forgeguard tests
git diff --check
git status --short
```

Expected: specialty 10/10; full suite 50 tests with only the two known Windows skips when applicable; demo emits five events and exits `0`; compileall/diff check exit `0`. `git status --short` must contain no policy-check implementation files; pre-existing unrelated user changes may remain and must be reported rather than staged, reverted, or deleted.

- [ ] **Micro-task 8 (2–5 min): Request final whole-branch review**

Use `superpowers:requesting-code-review` against the merge base with `main`. The reviewer must separately assess:

1. spec compliance: strict parser reuse, all six Actions, exact JSON/exit contract, config parity, and real TDD evidence;
2. code quality/security: no execution path, no approval creation, secret safety, error handling, duplication, deterministic tests, and Python 3.7 compatibility.

Fix every Critical or Important finding, rerun the scoped tests, request scoped re-review, and repeat Task 5's post-commit verification before claiming completion.

---

## Plan Completion Criteria

Implementation is ready for `superpowers:finishing-a-development-branch` only when all of the following are evidenced:

- Every functional test was written and observed failing before its implementation change.
- Tasks 1–4 have separate commits and clean two-stage reviews.
- `policy-check` never constructs runtime services or executes an Action under allow, deny, or require_approval.
- Success and error JSON, stdin behavior, config parity, secret redaction, and all four exit codes are covered deterministically.
- README examples execute successfully and the demo proves a dangerous command had no side effect.
- Specialty tests, all 50 repository tests, demo, compileall, diff check, credential scan, and example-marker scan have fresh evidence.
- `AGENT_LOG.md` records only events that actually occurred.
- Final whole-branch review has no unresolved Critical or Important findings.
