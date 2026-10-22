"""JSON lines on stdout for the request log (#56), when LOG_FORMAT=json.

Same fields as the OTLP record, plus the trace and span IDs in hex, so a line
from `docker compose logs app` can be matched to its trace. Outside a span's
context the two ID fields are left out, not empty.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from opentelemetry import trace

FIELDS = (
    "http.route",
    "http.request.method",
    "http.response.status_code",
    "duration_ms",
    "exception.type",
)


class JsonLineFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC)
        line = {
            "timestamp": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": self.service,
        }
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            line["trace_id"] = format(context.trace_id, "032x")
            line["span_id"] = format(context.span_id, "016x")
        for key in FIELDS:
            if key in record.__dict__:
                line[key] = record.__dict__[key]
        return json.dumps(line)
