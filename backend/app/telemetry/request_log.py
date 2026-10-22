"""One "request completed" record per API request (#56).

Runs inside the OpenTelemetry middleware, so the record is written while the
server span's context is current and carries its trace and span IDs. Fields
are fixed: method, route template, status, duration; an unhandled exception
adds one ERROR record with the exception type only, never its message.
"""

from __future__ import annotations

import logging
import time

from opentelemetry import trace
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_LOGGER = "tennis.requests"


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger(REQUEST_LOGGER)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        status = 500
        start = time.perf_counter()

        async def send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception as exc:
            self.logger.error("unhandled exception", extra={"exception.type": type(exc).__name__})
            raise
        finally:
            fields = {
                "http.request.method": scope["method"],
                "http.response.status_code": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }
            # The instrumentation resolved the full template, /api prefix
            # included; scope["route"] only knows the router-relative path.
            span_attributes = getattr(trace.get_current_span(), "attributes", None) or {}
            if "http.route" in span_attributes:  # absent when no route matched
                fields["http.route"] = span_attributes["http.route"]
            self.logger.info("request completed", extra=fields)
