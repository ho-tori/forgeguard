import json

from .models import Action


class ActionParseError(ValueError):
    pass


SCHEMAS = {
    "read_file": ({"path"}, set(), {"path": str}),
    "write_file": ({"path", "content"}, set(), {"path": str, "content": str}),
    "run_command": ({"argv"}, {"timeout"}, {"argv": list, "timeout": (int, float)}),
    "run_feedback": ({"check"}, set(), {"check": str}),
    "remember": ({"kind", "content"}, {"tags"}, {"kind": str, "content": str, "tags": list}),
    "finish": ({"summary"}, set(), {"summary": str}),
}


def parse_action(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ActionParseError("Model output must be a non-empty JSON string")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ActionParseError("Model output is not valid JSON: %s" % exc)
    if not isinstance(value, dict) or set(value) != {"action", "arguments"}:
        raise ActionParseError("Top-level object must contain only action and arguments")
    name = value["action"]
    arguments = value["arguments"]
    if name not in SCHEMAS:
        raise ActionParseError("Unknown action: %r" % name)
    if not isinstance(arguments, dict):
        raise ActionParseError("arguments must be an object")
    required, optional, types = SCHEMAS[name]
    fields = set(arguments)
    missing = required - fields
    unknown = fields - required - optional
    if missing or unknown:
        raise ActionParseError("Invalid fields for %s; missing=%s unknown=%s" % (name, sorted(missing), sorted(unknown)))
    for field, value_type in types.items():
        if field in arguments and not isinstance(arguments[field], value_type):
            raise ActionParseError("%s.%s has the wrong type" % (name, field))
    if name == "run_command":
        argv = arguments["argv"]
        if not argv or not all(isinstance(item, str) and item for item in argv):
            raise ActionParseError("run_command.argv must be a non-empty string array")
    if name == "remember" and "tags" in arguments:
        if not all(isinstance(item, str) for item in arguments["tags"]):
            raise ActionParseError("remember.tags must contain only strings")
    return Action(name, arguments)

