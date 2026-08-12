from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Action:
    name: str
    arguments: Dict[str, Any]


@dataclass
class Observation:
    ok: bool
    code: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self):
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }


@dataclass
class PolicyDecision:
    verdict: str
    reason: str
    risk: Optional[str] = None


@dataclass
class ApprovalRequest:
    id: str
    action_digest: str
    risk: str
    status: str
    created_at: float
    expires_at: float


@dataclass
class Memory:
    id: int
    session_id: str
    kind: str
    content: str
    tags: List[str]
    created_at: str


@dataclass
class AuditVerification:
    ok: bool
    records: int
    error: Optional[str] = None


@dataclass
class AgentResult:
    session_id: str
    state: str
    steps: int
    summary: Optional[str] = None
    approval_id: Optional[str] = None
    pending_action: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    message: Optional[str] = None

    def as_dict(self):
        return {
            "session_id": self.session_id,
            "state": self.state,
            "steps": self.steps,
            "summary": self.summary,
            "approval_id": self.approval_id,
            "pending_action": self.pending_action,
            "error_code": self.error_code,
            "message": self.message,
        }

