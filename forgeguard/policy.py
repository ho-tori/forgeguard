import os
import re

from .models import PolicyDecision


class WorkspaceViolation(ValueError):
    pass


class WorkspaceBoundary:
    def __init__(self, root):
        self.root = os.path.realpath(os.path.abspath(root))

    def resolve(self, relative_path):
        if not isinstance(relative_path, str) or not relative_path or "\x00" in relative_path:
            raise WorkspaceViolation("Path must be a non-empty string")
        candidate = os.path.realpath(os.path.abspath(os.path.join(self.root, relative_path)))
        try:
            inside = os.path.commonpath([self.root, candidate]) == self.root
        except ValueError:
            inside = False
        if not inside:
            raise WorkspaceViolation("Path escapes the configured workspace")
        return candidate


class PolicyEngine:
    SHELL_META = re.compile(r"(?:&&|\|\||[|;<>`]|\$\(|\r|\n)")
    PATH_ACTIONS = {"read_file", "write_file"}

    def __init__(self, workspace, allowed_commands=None, protected_paths=None):
        self.boundary = WorkspaceBoundary(workspace)
        self.allowed_commands = set(allowed_commands or ["python", "python3", "git"])
        defaults = [os.path.join(self.boundary.root, ".git"), os.path.join(self.boundary.root, ".forgeguard")]
        self.protected_paths = [os.path.realpath(os.path.abspath(path)) for path in defaults + list(protected_paths or [])]

    def evaluate(self, action):
        if action.name in self.PATH_ACTIONS:
            try:
                resolved = self.boundary.resolve(action.arguments.get("path"))
            except WorkspaceViolation as exc:
                return PolicyDecision("deny", str(exc), "workspace_escape")
            for protected_root in self.protected_paths:
                try:
                    if os.path.commonpath([protected_root, resolved]) == protected_root:
                        return PolicyDecision("deny", "Harness state and Git metadata are protected", "protected_path")
                except ValueError:
                    pass
            basename = os.path.basename(resolved).lower()
            if basename == ".env" or basename.startswith(".env.") or basename.endswith((".pem", ".key", ".p12", ".pfx")):
                return PolicyDecision("deny", "Known credential file types are protected", "protected_path")
            return PolicyDecision("allow", "Path is inside the configured workspace")
        if action.name != "run_command":
            return PolicyDecision("allow", "No elevated risk rule matched")
        argv = action.arguments.get("argv", [])
        if not argv or not all(isinstance(part, str) and part for part in argv):
            return PolicyDecision("deny", "Command argv is invalid", "invalid_command")
        if any(self.SHELL_META.search(part) for part in argv):
            return PolicyDecision("deny", "Shell syntax is forbidden; pass literal argv only", "shell_syntax")
        executable = argv[0]
        executable_base = os.path.basename(executable).lower()
        allowed_bare = {item.lower() for item in self.allowed_commands if not os.path.dirname(item)}
        allowed_full = {
            os.path.normcase(os.path.realpath(os.path.abspath(item)))
            for item in self.allowed_commands
            if os.path.dirname(item)
        }
        executable_has_path = bool(os.path.dirname(executable))
        full_match = executable_has_path and os.path.normcase(os.path.realpath(os.path.abspath(executable))) in allowed_full
        bare_match = not executable_has_path and executable.lower() in allowed_bare
        if not full_match and not bare_match:
            return PolicyDecision("deny", "Executable is not in the allowlist", "unknown_executable")
        lowered = [part.lower() for part in argv]
        if executable_base in ("git", "git.exe"):
            if any(part in ("-C", "--git-dir", "--work-tree") or part.startswith("--git-dir=") or part.startswith("--work-tree=") for part in argv[1:]):
                return PolicyDecision("deny", "Git may not redirect its working tree or metadata", "workspace_escape")
            if len(lowered) > 1 and lowered[1] in ("push", "clean"):
                return PolicyDecision("require_approval", "Network publication or destructive cleanup", "external_or_destructive_git")
            if len(lowered) > 2 and lowered[1] == "reset" and "--hard" in lowered[2:]:
                return PolicyDecision("require_approval", "Destructive Git reset", "destructive_git")
            if len(lowered) > 1 and lowered[1] in ("checkout", "restore") and any(part == "." for part in lowered[2:]):
                return PolicyDecision("require_approval", "Broad working-tree overwrite", "destructive_git")
            safe_status_flags = {"--short", "--porcelain", "--porcelain=v1", "--porcelain=v2", "--branch", "-b", "--ignored"}
            safe_status = (
                len(lowered) >= 2
                and lowered[1] == "status"
                and all(part in safe_status_flags or part.startswith("--untracked-files=") for part in lowered[2:])
            )
            if not safe_status:
                return PolicyDecision("require_approval", "Only a constrained git status is read-only without approval", "git_operation")
            return PolicyDecision("allow", "Constrained git status is read-only")
        if executable_base in ("pip", "pip.exe", "npm", "npm.cmd") and "install" in lowered[1:]:
            return PolicyDecision("require_approval", "Dependency installation changes the environment", "dependency_install")
        if executable_base.startswith("python") or executable.lower().endswith(("python.exe", "python3.exe")):
            return PolicyDecision("require_approval", "Arbitrary interpreter execution can bypass file and process controls", "arbitrary_code")
        return PolicyDecision("require_approval", "External processes can change files or external state", "external_process")
