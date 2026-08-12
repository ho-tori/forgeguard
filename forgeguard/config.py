import json
import os
import sys
from dataclasses import dataclass


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    workspace: str
    state_dir: str
    endpoint: str
    model: str
    max_steps: int
    command_timeout: int
    output_limit: int
    allowed_commands: list
    feedback_checks: dict
    bind: str
    port: int
    require_feedback: bool


DEFAULTS = {
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-5-mini",
    "max_steps": 12,
    "command_timeout": 60,
    "output_limit": 12000,
    "allowed_commands": ["python", "python3", "git"],
    "feedback_checks": {
        "unit": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    },
    "bind": "127.0.0.1",
    "port": 8080,
    "require_feedback": True,
}

SECRET_KEYS = {"api_key", "apikey", "password", "secret", "token", "authorization"}
ALLOWED_KEYS = set(DEFAULTS) | {"state_dir"}


def _reject_secrets(value, path="config"):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in SECRET_KEYS:
                raise ConfigError("Secrets are forbidden in config files (%s.%s)" % (path, key))
            _reject_secrets(child, "%s.%s" % (path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secrets(child, "%s[%s]" % (path, index))


def load_config(path=None, workspace=None):
    workspace = os.path.realpath(os.path.abspath(workspace or os.getcwd()))
    values = dict(DEFAULTS)
    values["allowed_commands"] = list(DEFAULTS["allowed_commands"])
    values["feedback_checks"] = dict(DEFAULTS["feedback_checks"])
    if path:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                supplied = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ConfigError("Cannot read config: %s" % exc)
        if not isinstance(supplied, dict):
            raise ConfigError("Config must be a JSON object")
        _reject_secrets(supplied)
        unknown = set(supplied) - ALLOWED_KEYS
        if unknown:
            raise ConfigError("Unknown config fields: %s" % sorted(unknown))
        values.update(supplied)
    state_dir = values.pop("state_dir", ".forgeguard")
    if not os.path.isabs(state_dir):
        state_dir = os.path.join(workspace, state_dir)
    executable = sys.executable
    for command in (executable, os.path.basename(executable)):
        if command not in values["allowed_commands"]:
            values["allowed_commands"].append(command)
    if not isinstance(values["max_steps"], int) or not 1 <= values["max_steps"] <= 100:
        raise ConfigError("max_steps must be an integer from 1 to 100")
    if not isinstance(values["port"], int) or not 0 <= values["port"] <= 65535:
        raise ConfigError("port must be an integer from 0 to 65535")
    if not isinstance(values["feedback_checks"], dict):
        raise ConfigError("feedback_checks must be an object")
    for name, argv in values["feedback_checks"].items():
        if not isinstance(name, str) or not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ConfigError("Every feedback check must be a non-empty argv array")
    return Config(workspace=workspace, state_dir=os.path.abspath(state_dir), **values)
