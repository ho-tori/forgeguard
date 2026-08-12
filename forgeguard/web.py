import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


MAX_REQUEST_BYTES = 256000
LOOPBACKS = {"127.0.0.1", "::1", "localhost"}


def validate_bind_security(host, admin_token):
    if host not in LOOPBACKS and (not admin_token or len(admin_token) < 16):
        raise ValueError("Non-loopback binding requires an admin token of at least 16 characters")


def create_server(host, port, service, admin_token=None):
    validate_bind_security(host, admin_token)

    class Handler(BaseHTTPRequestHandler):
        server_version = "ForgeGuard/0.1"

        def log_message(self, format_string, *args):
            return

        def _authorized(self):
            if admin_token is None and not self._trusted_host():
                return False
            if admin_token is None:
                return True
            provided = self.headers.get("Authorization", "")
            expected = "Bearer " + admin_token
            return hmac.compare_digest(provided, expected)

        def _trusted_host(self):
            supplied = self.headers.get("Host", "").strip().lower()
            if supplied.startswith("["):
                hostname = supplied[1:].split("]", 1)[0]
            else:
                hostname = supplied.split(":", 1)[0]
            return hostname in LOOPBACKS

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise ValueError("Content-Type must be application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Invalid Content-Length")
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("Request body size is invalid")
            try:
                value = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeError, ValueError) as exc:
                raise ValueError("Body must be valid UTF-8 JSON: %s" % exc)
            if not isinstance(value, dict):
                raise ValueError("Body must be a JSON object")
            return value

        def _serve_index(self):
            path = os.path.join(os.path.dirname(__file__), "static", "index.html")
            with open(path, "rb") as handle:
                body = handle.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/health":
                return self._json(200, {"status": "ok"})
            if path == "/":
                if not self._authorized():
                    return self._json(403, {"error_code": "untrusted_host"})
                return self._serve_index()
            if path == "/api/status":
                if not self._authorized():
                    return self._json(403 if admin_token is None else 401, {"error_code": "unauthorized"})
                return self._json(200, {"credential": service.credential_status(), "audit": service.audit_status()})
            return self._json(404, {"error_code": "not_found"})

        def do_POST(self):
            if not self._authorized():
                return self._json(401, {"error_code": "unauthorized"})
            path = urlparse(self.path).path
            try:
                body = self._body()
                if path == "/api/run":
                    if set(body) != {"task"} or not isinstance(body["task"], str):
                        raise ValueError("Expected only a string task")
                    payload, status = service.run_task(body["task"])
                    return self._json(status, payload)
                if path == "/api/approval":
                    if set(body) != {"session_id", "approval_id", "approved"} or not isinstance(body["approved"], bool):
                        raise ValueError("Expected session_id, approval_id and boolean approved")
                    payload, status = service.decide_approval(body["session_id"], body["approval_id"], body["approved"])
                    return self._json(status, payload)
                if path == "/api/credential":
                    if set(body) != {"api_key"} or not isinstance(body["api_key"], str):
                        raise ValueError("Expected only a string api_key")
                    return self._json(200, {"credential": service.credential_set(body["api_key"])})
                if path == "/api/credential/clear":
                    if body:
                        raise ValueError("Credential clear expects an empty object")
                    return self._json(200, {"credential": service.credential_clear()})
                return self._json(404, {"error_code": "not_found"})
            except (ValueError, RuntimeError, OSError) as exc:
                return self._json(400, {"error_code": "invalid_request", "message": str(exc)})

    return ThreadingHTTPServer((host, port), Handler)
