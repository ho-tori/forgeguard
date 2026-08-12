import json
import os
import sys
import tempfile

from .agent import Agent
from .approval import ApprovalStore
from .audit import AuditLog
from .llm import MockLLM
from .memory import MemoryStore
from .models import Action
from .policy import PolicyEngine
from .tools import ToolRegistry


def _reply(action, **arguments):
    return json.dumps({"action": action, "arguments": arguments})


def run_demo(stream=None):
    stream = stream or sys.stdout
    with tempfile.TemporaryDirectory(prefix="forgeguard-demo-") as workspace:
        executable = sys.executable
        policy = PolicyEngine(workspace, ["git", executable, os.path.basename(executable)])
        memory = MemoryStore(os.path.join(workspace, ".forgeguard", "memory.db"))
        approvals = ApprovalStore(os.path.join(workspace, ".forgeguard", "approvals.db"))
        audit = AuditLog(os.path.join(workspace, ".forgeguard", "audit.jsonl"))
        tools = ToolRegistry(
            workspace,
            policy,
            memory=memory,
            feedback_checks={
                "unit": [
                    executable,
                    "-c",
                    "import pathlib,sys;sys.exit(0 if pathlib.Path('answer.txt').read_text()=='fixed' else 1)",
                ]
            },
        )
        llm = MockLLM(
            [
                _reply("run_command", argv=["git", "reset", "--hard"]),
                _reply("write_file", path="answer.txt", content="wrong"),
                _reply("run_feedback", check="unit"),
                _reply("write_file", path="answer.txt", content="fixed"),
                _reply("run_feedback", check="unit"),
                _reply("finish", summary="Objective feedback drove the correction."),
            ]
        )
        agent = Agent(llm, tools, policy, approvals, audit, memory, max_steps=10)

        waiting = agent.run("Demonstrate governance and feedback correction")
        _emit(stream, "1_guardrail", {"state": waiting.state, "risk": waiting.pending_action["risk"]})

        # Prove the approval cannot be swapped to another dangerous action.
        approvals.decide(waiting.approval_id, approved=True)
        swapped = Action("run_command", {"argv": ["git", "push", "--force"]})
        swap_blocked = not approvals.consume(waiting.approval_id, swapped)
        original_consumed = approvals.consume(
            waiting.approval_id,
            Action(waiting.pending_action["action"], waiting.pending_action["arguments"]),
        )
        replay_blocked = not approvals.consume(
            waiting.approval_id,
            Action(waiting.pending_action["action"], waiting.pending_action["arguments"]),
        )
        _emit(
            stream,
            "2_approval_binding",
            {"swap_blocked": swap_blocked, "original_consumed": original_consumed, "replay_blocked": replay_blocked},
        )

        # A fresh agent runs the deterministic failure -> correction sequence.
        correction_llm = MockLLM(llm.responses)
        correction_agent = Agent(correction_llm, tools, policy, approvals, audit, memory, max_steps=10)
        result = correction_agent.run("Use objective feedback to produce answer.txt")
        next_turn_saw_failure = "feedback_failed" in json.dumps(correction_llm.calls[2])
        with open(os.path.join(workspace, "answer.txt"), encoding="utf-8") as handle:
            final_content = handle.read()
        _emit(
            stream,
            "3_feedback_loop",
            {
                "state": result.state,
                "summary": result.summary,
                "next_turn_saw_failure": next_turn_saw_failure,
                "final_content": final_content,
            },
        )
        verification = audit.verify()
        _emit(stream, "4_audit", {"ok": verification.ok, "records": verification.records})
        memory.close()
        return bool(
            waiting.state == "awaiting_approval"
            and swap_blocked
            and original_consumed
            and replay_blocked
            and result.state == "completed"
            and next_turn_saw_failure
            and verification.ok
        )


def _emit(stream, name, payload):
    stream.write(json.dumps({"demo": name, **payload}, sort_keys=True) + "\n")
