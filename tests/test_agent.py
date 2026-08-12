import json
import os
import sys
import tempfile
import unittest

from forgeguard.agent import Agent
from forgeguard.approval import ApprovalStore
from forgeguard.audit import AuditLog
from forgeguard.llm import MockLLM
from forgeguard.memory import MemoryStore
from forgeguard.policy import PolicyEngine
from forgeguard.tools import ToolRegistry


def reply(action, **arguments):
    return json.dumps({"action": action, "arguments": arguments})


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = self.temp.name
        self.policy = PolicyEngine(root, allowed_commands=["git", os.path.basename(sys.executable), sys.executable])
        self.tools = ToolRegistry(
            root,
            self.policy,
            feedback_checks={"unit": [sys.executable, "-c", "import pathlib,sys; sys.exit(0 if pathlib.Path('answer.txt').read_text() == 'fixed' else 1)"]},
        )
        self.approvals = ApprovalStore(os.path.join(root, ".forgeguard", "approvals.db"))
        self.audit = AuditLog(os.path.join(root, ".forgeguard", "audit.jsonl"))
        self.memory = MemoryStore(os.path.join(root, ".forgeguard", "memory.db"))

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def make_agent(self, responses, max_steps=8):
        llm = MockLLM(responses)
        return Agent(llm, self.tools, self.policy, self.approvals, self.audit, self.memory, max_steps=max_steps), llm

    def test_failure_feedback_reaches_next_turn_and_drives_correction(self):
        agent, llm = self.make_agent([
            reply("write_file", path="answer.txt", content="wrong"),
            reply("run_feedback", check="unit"),
            reply("write_file", path="answer.txt", content="fixed"),
            reply("run_feedback", check="unit"),
            reply("finish", summary="fixed after objective feedback"),
        ])
        result = agent.run("Create the expected answer")
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.summary, "fixed after objective feedback")
        third_call = json.dumps(llm.calls[2])
        self.assertIn("feedback_failed", third_call)

    def test_dangerous_action_stops_before_tool_and_resumes_only_after_approval(self):
        agent, unused = self.make_agent([
            reply("run_command", argv=["git", "reset", "--hard"]),
            reply("finish", summary="done"),
        ])
        waiting = agent.run("Reset the repository")
        self.assertEqual(waiting.state, "awaiting_approval")
        self.assertIsNotNone(waiting.approval_id)
        approved = agent.resume(waiting.session_id, waiting.approval_id, approved=True)
        self.assertIn(approved.state, ("running", "completed"))
        events = [item["event"] for item in self.audit.read_all()]
        self.assertIn("approval_required", events)
        self.assertIn("approval_consumed", events)

    def test_finish_requires_fresh_passing_feedback(self):
        agent, unused = self.make_agent([
            reply("finish", summary="premature"),
            reply("write_file", path="answer.txt", content="fixed"),
            reply("run_feedback", check="unit"),
            reply("finish", summary="verified"),
        ])
        result = agent.run("Do verified work")
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.summary, "verified")

    def test_even_a_failed_command_invalidates_previous_feedback(self):
        agent, unused = self.make_agent([
            reply("write_file", path="answer.txt", content="fixed"),
            reply("run_feedback", check="unit"),
            reply("run_command", argv=[sys.executable, "-c", "raise SystemExit(1)"]),
            reply("finish", summary="must be rejected as stale"),
            reply("run_feedback", check="unit"),
            reply("finish", summary="freshly verified"),
        ])
        waiting = agent.run("Do work and execute a potentially mutating command")
        self.assertEqual(waiting.state, "awaiting_approval")
        result = agent.resume(waiting.session_id, waiting.approval_id, approved=True)
        if result.state == "running":
            result = agent.continue_session(waiting.session_id)
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.summary, "freshly verified")

    def test_max_steps_stops_run(self):
        agent, unused = self.make_agent([reply("read_file", path="missing") for _ in range(3)], max_steps=2)
        result = agent.run("Never finish")
        self.assertEqual(result.state, "failed")
        self.assertEqual(result.error_code, "max_steps")


if __name__ == "__main__":
    unittest.main()
