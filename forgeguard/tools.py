import os
import subprocess
import tempfile
import time
import re

from .memory import SecretDetected, contains_secret, redact_secrets
from .models import Observation


class ToolRegistry:
    SENSITIVE_ENV = re.compile(r"(?i)(api.?key|token|secret|password|credential|authorization)")
    def __init__(
        self,
        workspace,
        policy,
        feedback_checks=None,
        memory=None,
        command_timeout=30,
        output_limit=12000,
        file_limit=200000,
    ):
        self.workspace = os.path.realpath(os.path.abspath(workspace))
        self.policy = policy
        self.feedback_checks = feedback_checks or {}
        self.memory = memory
        self.command_timeout = command_timeout
        self.output_limit = output_limit
        self.file_limit = file_limit

    def execute(self, action, approved=False, session_id=None):
        decision = self.policy.evaluate(action)
        if decision.verdict == "deny":
            return Observation(False, "policy_denied", decision.reason, {"risk": decision.risk})
        if decision.verdict == "require_approval" and not approved:
            return Observation(False, "approval_required", decision.reason, {"risk": decision.risk})
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "run_command": self._run_command,
            "run_feedback": self._run_feedback,
        }
        if action.name == "remember":
            return self._remember(action.arguments, session_id)
        handler = handlers.get(action.name)
        if handler is None:
            return Observation(False, "unknown_tool", "No executable tool for action %s" % action.name)
        try:
            return handler(action.arguments)
        except (OSError, UnicodeError, ValueError) as exc:
            return Observation(False, "tool_error", str(exc))

    def _read_file(self, arguments):
        path = self.policy.boundary.resolve(arguments["path"])
        if not os.path.isfile(path):
            return Observation(False, "file_not_found", "File does not exist")
        size = os.path.getsize(path)
        if size > self.file_limit:
            return Observation(False, "file_too_large", "File exceeds the configured read limit", {"size": size})
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read(self.file_limit + 1)
        if contains_secret(content):
            return Observation(False, "secret_detected", "File appears to contain a credential and was not returned")
        return Observation(True, "file_read", "Read file", {"path": arguments["path"], "content": content})

    def _write_file(self, arguments):
        if contains_secret(arguments["content"]):
            return Observation(False, "secret_detected", "Refusing to write content that appears to contain a credential")
        encoded = arguments["content"].encode("utf-8")
        if len(encoded) > self.file_limit:
            return Observation(False, "file_too_large", "Content exceeds the configured write limit")
        path = self.policy.boundary.resolve(arguments["path"])
        parent = os.path.dirname(path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        descriptor, temporary = tempfile.mkstemp(prefix=".forgeguard-write-", dir=parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return Observation(True, "file_written", "Wrote file atomically", {"path": arguments["path"], "bytes": len(encoded)})

    def _run_process(self, argv, timeout):
        started = time.monotonic()
        environment = {key: value for key, value in os.environ.items() if not self.SENSITIVE_ENV.search(key)}
        argv = list(argv)
        if not os.path.dirname(argv[0]):
            argv[0] = self._resolve_bare_executable(argv[0], environment)
        try:
            process = subprocess.run(
                argv,
                cwd=self.workspace,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                universal_newlines=True,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            return Observation(
                False,
                "command_timeout",
                "Command exceeded %.1f seconds" % timeout,
                {
                    "argv": [redact_secrets(part) for part in argv],
                    "stdout": self._truncate(self._decode_timeout_output(exc.stdout)),
                    "stderr": self._truncate(self._decode_timeout_output(exc.stderr)),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                },
            )
        data = {
            "argv": [redact_secrets(part) for part in argv],
            "exit_code": process.returncode,
            "stdout": self._truncate(process.stdout),
            "stderr": self._truncate(process.stderr),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        if process.returncode == 0:
            return Observation(True, "command_passed", "Command completed successfully", data)
        return Observation(False, "command_failed", "Command exited with code %s" % process.returncode, data)

    def _run_command(self, arguments):
        requested = float(arguments.get("timeout", self.command_timeout))
        timeout = max(0.1, min(requested, float(self.command_timeout)))
        return self._run_process(arguments["argv"], timeout)

    def _run_feedback(self, arguments):
        check = arguments["check"]
        argv = self.feedback_checks.get(check)
        if argv is None:
            return Observation(False, "unknown_feedback_check", "Unknown feedback check: %s" % check)
        observation = self._run_process(argv, self.command_timeout)
        observation.code = "feedback_passed" if observation.ok else "feedback_failed"
        observation.message = "Feedback check %s %s" % (check, "passed" if observation.ok else "failed")
        observation.data["check"] = check
        return observation

    def _remember(self, arguments, session_id):
        if self.memory is None:
            return Observation(False, "memory_unavailable", "No memory store is configured")
        try:
            memory_id = self.memory.add(
                session_id or "unknown",
                arguments["kind"],
                arguments["content"],
                arguments.get("tags", []),
            )
        except SecretDetected as exc:
            return Observation(False, "secret_detected", str(exc))
        return Observation(True, "memory_saved", "Saved project memory", {"id": memory_id})

    def _truncate(self, value):
        value = value or ""
        value = redact_secrets(value)
        if len(value) <= self.output_limit:
            return value
        return value[: self.output_limit] + "\n...[truncated]"

    @staticmethod
    def _decode_timeout_output(value):
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value or ""

    def _resolve_bare_executable(self, name, environment):
        extensions = [""]
        if os.name == "nt" and not os.path.splitext(name)[1]:
            extensions = [item.lower() for item in environment.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep)]
        for directory in os.get_exec_path(environment):
            if not directory or not os.path.isabs(directory):
                continue
            for extension in extensions:
                candidate = os.path.realpath(os.path.join(directory, name + extension))
                try:
                    if os.path.commonpath([self.workspace, candidate]) == self.workspace:
                        continue
                except ValueError:
                    pass
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    return candidate
        raise OSError("Executable was not found in trusted absolute PATH directories: %s" % name)
