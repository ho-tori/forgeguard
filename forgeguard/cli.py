import argparse
import getpass
import json
import os
import sys

from .config import ConfigError, load_config
from .credentials import CredentialError, CredentialManager
from .demo import run_demo
from .service import ForgeGuardService
from .web import create_server


def build_parser():
    parser = argparse.ArgumentParser(prog="forgeguard", description="Governed coding-agent harness")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace root (default: current directory)")
    parser.add_argument("--config", help="Path to JSON config (secrets are forbidden)")
    commands = parser.add_subparsers(dest="command")

    run = commands.add_parser("run", help="Run one task")
    run.add_argument("task", nargs="?", help="Task text; reads stdin when omitted")

    serve = commands.add_parser("serve", help="Start the WebUI")
    serve.add_argument("--bind", help="Override configured bind address")
    serve.add_argument("--port", type=int, help="Override configured port")
    serve.add_argument("--admin-token-file", help="Required for non-loopback binding; mode 600 on POSIX")

    credential = commands.add_parser("credential", help="Manage the provider credential")
    credential.add_argument("operation", choices=["set", "status", "clear"])

    commands.add_parser("audit-verify", help="Verify the audit hash chain")
    commands.add_parser("memory-clear", help="Clear project memory")
    commands.add_parser("demo", help="Run deterministic offline mechanism demo")
    return parser


def _read_token(path):
    if not path:
        return None
    if os.name != "nt" and os.stat(path).st_mode & 0o077:
        raise PermissionError("Admin token file must use mode 600")
    with open(path, "r", encoding="utf-8") as handle:
        value = handle.read().strip()
    if len(value) < 16:
        raise ValueError("Admin token must contain at least 16 characters")
    return value


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.command:
        build_parser().print_help()
        return 2
    try:
        if args.command == "demo":
            return 0 if run_demo() else 1
        credentials = CredentialManager()
        if args.command == "credential":
            if args.operation == "set":
                first = getpass.getpass("API key: ")
                second = getpass.getpass("Confirm API key: ")
                if first != second:
                    raise CredentialError("Credential confirmation does not match")
                credentials.set(first)
            elif args.operation == "clear":
                credentials.clear()
            print(json.dumps(credentials.status(), sort_keys=True))
            return 0

        config = load_config(args.config, workspace=args.workspace)
        service = ForgeGuardService(config, credentials=credentials)
        try:
            if args.command == "run":
                task = args.task if args.task is not None else sys.stdin.read()
                payload, status = service.run_task(task)
                print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
                return 0 if status == 200 and payload.get("state") in ("completed", "awaiting_approval") else 1
            if args.command == "audit-verify":
                payload = service.audit_status()
                print(json.dumps(payload, sort_keys=True))
                return 0 if payload["ok"] else 1
            if args.command == "memory-clear":
                service.memory.clear()
                print(json.dumps({"cleared": True}))
                return 0
            if args.command == "serve":
                host = args.bind or config.bind
                port = args.port if args.port is not None else config.port
                token = _read_token(args.admin_token_file)
                server = create_server(host, port, service, admin_token=token)
                print("ForgeGuard WebUI listening on http://%s:%s" % server.server_address, flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
                return 0
        finally:
            service.close()
    except (ConfigError, CredentialError, OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 2

