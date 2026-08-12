import os
import threading

from .agent import Agent
from .approval import ApprovalStore
from .audit import AuditLog
from .credentials import CredentialManager
from .llm import OpenAICompatibleLLM
from .memory import MemoryStore
from .policy import PolicyEngine
from .tools import ToolRegistry


class ForgeGuardService:
    def __init__(self, config, credentials=None, llm=None):
        self.config = config
        if not os.path.exists(config.state_dir):
            os.makedirs(config.state_dir)
        self.credentials = credentials or CredentialManager()
        self.audit = AuditLog(os.path.join(config.state_dir, "audit.jsonl"))
        self.memory = MemoryStore(os.path.join(config.state_dir, "memory.db"))
        self.approvals = ApprovalStore(os.path.join(config.state_dir, "approvals.db"))
        self.policy = PolicyEngine(config.workspace, config.allowed_commands, protected_paths=[config.state_dir])
        self.tools = ToolRegistry(
            config.workspace,
            self.policy,
            feedback_checks=config.feedback_checks,
            memory=self.memory,
            command_timeout=config.command_timeout,
            output_limit=config.output_limit,
        )
        if llm is None:
            llm = OpenAICompatibleLLM(config.endpoint, config.model, self.credentials.get)
        self.agent = Agent(
            llm,
            self.tools,
            self.policy,
            self.approvals,
            self.audit,
            self.memory,
            max_steps=config.max_steps,
            require_feedback=config.require_feedback,
        )
        self.run_lock = threading.Lock()
        self.active_session_id = None

    def run_task(self, task):
        if not self.run_lock.acquire(False):
            return {"error_code": "task_in_progress", "message": "Only one task may run at a time"}, 409
        try:
            if self.active_session_id is not None:
                return {"error_code": "approval_pending", "message": "Resolve the pending approval before starting another task"}, 409
            result = self.agent.run(task)
            if result.state == "awaiting_approval":
                self.active_session_id = result.session_id
            return result.as_dict(), 200
        finally:
            self.run_lock.release()

    def decide_approval(self, session_id, approval_id, approved):
        if not self.run_lock.acquire(False):
            return {"error_code": "task_in_progress", "message": "Only one task may run at a time"}, 409
        try:
            if self.active_session_id != session_id:
                return {"error_code": "invalid_session", "message": "Session is not the active approval"}, 400
            result = self.agent.resume(session_id, approval_id, approved)
            if result.state == "running":
                result = self.agent.continue_session(session_id)
            self.active_session_id = result.session_id if result.state == "awaiting_approval" else None
            return result.as_dict(), 200 if result.error_code is None else 400
        finally:
            self.run_lock.release()

    def credential_status(self):
        return self.credentials.status()

    def credential_set(self, value):
        self.credentials.set(value)
        self.audit.append("system", "credential_set", {"configured": True})
        return self.credentials.status()

    def credential_clear(self):
        self.credentials.clear()
        self.audit.append("system", "credential_cleared", {"configured": False})
        return self.credentials.status()

    def audit_status(self):
        result = self.audit.verify()
        return {"ok": result.ok, "records": result.records, "error": result.error}

    def close(self):
        self.memory.close()
