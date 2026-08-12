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
