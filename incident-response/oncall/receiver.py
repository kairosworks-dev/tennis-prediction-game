"""POST /alerts on 127.0.0.1: the webhook Grafana's contact point calls.

Checks, in order, each answered before anything is saved or started:
415 not JSON -> 401 bad or missing bearer token -> 400 bad body ->
200 ignored (test notification, resolved only, datasource error) ->
200 busy (a run is in progress) -> 200 duplicate (the incident has a folder) ->
202 accepted (the run starts in the background).

Request headers are never saved: only the body reaches the incident folder.
"""

from __future__ import annotations

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Tuple
from urllib.parse import urlsplit

from .alerts import BadPayload, Ignored, classify
from .config import HOST, Settings
from .runner import Responder

PATH = "/alerts"
MAX_BODY = 1024 * 1024


class AlertHandler(BaseHTTPRequestHandler):
    server_version = "oncall-responder"
    sys_version = ""
    server: ResponderServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silence the default access log: it would print the request line only,
        and our own log line says more without any header."""

    def _answer(self, code: int, body: Dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if code == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="responder"')
        self.end_headers()
        self.wfile.write(data)
        # The method and path as sent (no query string, no header), cut short.
        path = urlsplit(self.path).path[:200]
        self.server.responder.log(f"{self.command} {path} -> {code} {body.get('message', body.get('status'))}")

    def _authorised(self) -> bool:
        header = self.headers.get("Authorization", "")
        scheme, _, presented = header.partition(" ")
        if scheme.lower() != "bearer" or not presented.strip():
            return False
        return hmac.compare_digest(
            presented.strip().encode("utf-8"), self.server.settings.token.encode("utf-8")
        )

    def _read_json(self) -> Tuple[bool, Any]:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return False, "a Content-Length header is required"
        if length < 0 or length > MAX_BODY:
            return False, f"the body must be between 0 and {MAX_BODY} bytes"
        raw = self.rfile.read(length)
        try:
            return True, json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return False, "the body is not valid JSON"

    def do_POST(self) -> None:  # noqa: N802
        if urlsplit(self.path).path != PATH:
            self._answer(404, {"status": "error", "message": "not found"})
            return
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._answer(415, {"status": "error", "message": "send application/json"})
            return
        if not self._authorised():
            self._answer(401, {"status": "error", "message": "missing or wrong token (Authorization header)"})
            return
        ok, payload = self._read_json()
        if not ok:
            self._answer(400, {"status": "error", "message": payload})
            return
        responder = self.server.responder
        try:
            decision = classify(payload, responder.clock())
        except BadPayload as error:
            self._answer(400, {"status": "error", "message": str(error)})
            return
        if isinstance(decision, Ignored):
            self._answer(
                200,
                {"status": "ignored", "reason": decision.reason, "message": f"ignored: {decision.reason}"},
            )
            return
        submission = responder.submit(decision)
        if submission.status == "accepted":
            self._answer(
                202,
                {"status": "accepted", "incident": submission.incident_id,
                 "message": f"accepted: incident {submission.incident_id}"},
            )
        elif submission.status == "busy":
            self._answer(
                200,
                {"status": "busy", "incident": submission.incident_id,
                 "message": f"busy: run {submission.incident_id} in progress, nothing started"},
            )
        else:
            self._answer(
                200,
                {"status": "duplicate", "incident": submission.incident_id,
                 "message": f"duplicate: incident {submission.incident_id} already handled"},
            )

    def _not_allowed(self) -> None:
        if urlsplit(self.path).path == PATH:
            self._answer(405, {"status": "error", "message": "use POST"})
        else:
            self._answer(404, {"status": "error", "message": "not found"})

    do_GET = do_PUT = do_DELETE = do_PATCH = _not_allowed  # noqa: N815


class ResponderServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, settings: Settings, responder: Responder, port: int) -> None:
        self.settings = settings
        self.responder = responder
        super().__init__((HOST, port), AlertHandler)


def make_server(settings: Settings, responder: Responder, port: int = -1) -> ResponderServer:
    """Bind 127.0.0.1 only. port=-1 means the configured port; 0 picks a free one."""
    return ResponderServer(settings, responder, settings.port if port < 0 else port)
