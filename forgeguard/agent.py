import json
import uuid

from .llm import LLMError
from .models import Action, AgentResult, Observation
from .parser import ActionParseError, parse_action


SYSTEM_PROMPT = """You are the decision component inside ForgeGuard, a coding-agent harness.
Return exactly one JSON object and no Markdown: {"action":"...","arguments":{...}}.
Available actions: read_file(path), write_file(path,content), run_command(argv,timeout?),
run_feedback(check), remember(kind,content,tags?), finish(summary).
Tool and policy results are authoritative. Correct failures before finishing. Never include secrets."""


class Agent:
    MUTATING_ACTIONS = {"write_file", "run_command"}

    def __init__(self, llm, tools, policy, approvals, audit, memory, max_steps=12, require_feedback=True):
        self.llm = llm
        self.tools = tools
        self.policy = policy
        self.approvals = approvals
        self.audit = audit
        self.memory = memory
        self.max_steps = max_steps
        self.require_feedback = require_feedback
        self.sessions = {}

    def run(self, task):
        if not isinstance(task, str) or not task.strip():
            return AgentResult("", "failed", 0, error_code="invalid_task", message="Task must not be empty")
        session_id = str(uuid.uuid4())
        memories = self.memory.search(task, limit=5)
        session = {
            "id": session_id,
            "task": task.strip(),
            "state": "running",
            "step": 0,
            "mutation": 0,
            "passed_feedback_mutation": -1,
            "history": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": task.strip(),
                            "available_feedback_checks": sorted(self.tools.feedback_checks),
                            "relevant_memory": [
                                {"kind": item.kind, "content": item.content, "tags": item.tags} for item in memories
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "pending": None,
        }
        self.sessions[session_id] = session
        self.audit.append(session_id, "session_started", {"task_length": len(task), "memory_count": len(memories)})
        return self._drive(session)

    def _drive(self, session):
        while session["state"] == "running" and session["step"] < self.max_steps:
            session["step"] += 1
            try:
                raw = self.llm.complete(session["history"])
            except LLMError as exc:
                return self._fail(session, "llm_error", str(exc))
            try:
                action = parse_action(raw)
            except ActionParseError as exc:
                observation = Observation(False, "invalid_action", str(exc))
                self._observe(session, raw, observation)
                continue
            self.audit.append(session["id"], "action_decided", {"step": session["step"], "action": action.name})
            if action.name == "finish":
                if self.require_feedback and session["passed_feedback_mutation"] != session["mutation"]:
                    self._observe(
                        session,
                        raw,
                        Observation(False, "verification_required", "Run a configured feedback check after the latest change"),
                    )
                    continue
                session["state"] = "completed"
                self.audit.append(session["id"], "session_completed", {"steps": session["step"]})
                return AgentResult(session["id"], "completed", session["step"], summary=action.arguments["summary"])
            decision = self.policy.evaluate(action)
            self.audit.append(
                session["id"],
                "policy_decision",
                {"action": action.name, "verdict": decision.verdict, "risk": decision.risk, "reason": decision.reason},
            )
            if decision.verdict == "require_approval":
                request = self.approvals.request(action, decision.risk or "unspecified")
                session["state"] = "awaiting_approval"
                session["pending"] = {"request": request, "action": action, "raw": raw}
                self.audit.append(
                    session["id"],
                    "approval_required",
                    {"approval_id": request.id, "action": action.name, "arguments": action.arguments, "risk": request.risk},
                )
                return AgentResult(
                    session["id"],
                    "awaiting_approval",
                    session["step"],
                    approval_id=request.id,
                    pending_action={"action": action.name, "arguments": action.arguments, "risk": request.risk},
                )
            observation = self.tools.execute(action, session_id=session["id"])
            self._apply_observation_state(session, action, observation)
            self._observe(session, raw, observation)
        if session["state"] == "running":
            return self._fail(session, "max_steps", "Agent reached its configured step limit")
        return self._result(session)

    def resume(self, session_id, approval_id, approved):
        session = self.sessions.get(session_id)
        if session is None or session["state"] != "awaiting_approval" or session["pending"] is None:
            return AgentResult(session_id, "failed", 0, error_code="invalid_session", message="No matching pending session")
        pending = session["pending"]
        if pending["request"].id != approval_id:
            return AgentResult(session_id, "failed", session["step"], error_code="approval_mismatch")
        if not self.approvals.decide(approval_id, approved):
            return AgentResult(session_id, "failed", session["step"], error_code="approval_already_decided")
        if not approved:
            session["state"] = "failed"
            self.audit.append(session_id, "approval_rejected", {"approval_id": approval_id})
            return AgentResult(session_id, "failed", session["step"], error_code="approval_rejected")
        action = pending["action"]
        if not self.approvals.consume(approval_id, action):
            return self._fail(session, "approval_invalid", "Approval expired, was changed, or was already consumed")
        self.audit.append(session_id, "approval_consumed", {"approval_id": approval_id, "action": action.name})
        observation = self.tools.execute(action, approved=True, session_id=session_id)
        session["state"] = "running"
        session["pending"] = None
        self._apply_observation_state(session, action, observation)
        self._observe(session, pending["raw"], observation)
        return self._result(session)

    def continue_session(self, session_id):
        session = self.sessions.get(session_id)
        if session is None or session["state"] != "running":
            return AgentResult(session_id, "failed", 0, error_code="invalid_session")
        return self._drive(session)

    def _apply_observation_state(self, session, action, observation):
        # A command may mutate before failing, so every dispatched command
        # invalidates earlier feedback. A failed write is atomic and does not.
        if action.name == "run_command" or (action.name == "write_file" and observation.ok):
            session["mutation"] += 1
        if action.name == "run_feedback" and observation.ok:
            session["passed_feedback_mutation"] = session["mutation"]

    def _observe(self, session, raw, observation):
        session["history"].append({"role": "assistant", "content": raw})
        session["history"].append(
            {"role": "user", "content": json.dumps({"observation": observation.as_dict()}, ensure_ascii=False)}
        )
        self.audit.append(
            session["id"],
            "tool_observation",
            {"step": session["step"], "ok": observation.ok, "code": observation.code, "message": observation.message},
        )

    def _fail(self, session, code, message):
        session["state"] = "failed"
        self.audit.append(session["id"], "session_failed", {"code": code, "message": message})
        return AgentResult(session["id"], "failed", session["step"], error_code=code, message=message)

    @staticmethod
    def _result(session):
        pending = session.get("pending")
        return AgentResult(
            session["id"],
            session["state"],
            session["step"],
            approval_id=pending["request"].id if pending else None,
        )
