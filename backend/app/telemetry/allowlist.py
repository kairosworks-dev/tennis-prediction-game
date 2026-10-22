"""The PII guard's first layer (#56): what may leave the process.

Every span, metric and log attribute whose key is not listed here is dropped
before export, so anything the instrumentation adds in a later release is
dropped by default instead of leaking. The Collector repeats the same lists
(telemetry/otel-collector.yaml); a test keeps the two in step.

Not listed on purpose: the user id, e-mail address, display name, cookies,
headers, bodies, query strings, client address, user agent, exception messages
and stack traces, and the source location the SDK's logging handler adds.
Telemetry carries the exception type only.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from opentelemetry.sdk._logs import ReadableLogRecord
from opentelemetry.sdk._logs.export import LogRecordExporter, LogRecordExportResult
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

RESOURCE_KEYS = frozenset(
    {
        "service.name",
        "service.namespace",
        "service.version",
        "service.instance.id",
        "deployment.environment.name",
        "telemetry.sdk.language",
        "telemetry.sdk.name",
        "telemetry.sdk.version",
    }
)

#: Spans keep the route template and, for a matched or unmatched request, the
#: path (path parameters such as a tournament id are not personal data).
SPAN_KEYS = frozenset(
    {
        "http.request.method",
        "http.response.status_code",
        "http.route",
        "url.path",
        "url.scheme",
        "network.protocol.name",
        "network.protocol.version",
        "error.type",
        "exception.type",
    }
)

#: Metric labels are a bounded set: never a path, never an id.
METRIC_KEYS = frozenset({"http.request.method", "http.response.status_code", "http.route"})

LOG_KEYS = frozenset(
    {
        "http.request.method",
        "http.response.status_code",
        "http.route",
        "duration_ms",
        "exception.type",
    }
)


def keep(attributes: Mapping[str, Any] | None, allowed: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in (attributes or {}).items() if key in allowed}


def safe_resource(resource: Resource) -> Resource:
    """The resource with only allowlisted keys; OTEL_RESOURCE_ATTRIBUTES is free text."""
    return Resource(keep(resource.attributes, RESOURCE_KEYS), resource.schema_url)


def metric_views() -> list[View]:
    """One catch-all view that keeps only the allowlisted metric attributes.

    A view merges the series that become identical once a key is gone, which a
    filter applied after aggregation could not do.
    """
    return [View(instrument_name="*", attribute_keys=set(METRIC_KEYS))]


def _scrub_span(span: ReadableSpan) -> ReadableSpan:
    status = span.status
    if status.status_code is StatusCode.ERROR:
        # The SDK fills the description with "Type: message" on an exception.
        status = Status(StatusCode.ERROR)
    events = [
        Event(event.name, keep(event.attributes, SPAN_KEYS), event.timestamp)
        for event in span.events
    ]
    return ReadableSpan(
        name=span.name,
        context=span.get_span_context(),
        parent=span.parent,
        resource=span.resource,
        attributes=keep(span.attributes, SPAN_KEYS),
        events=events,
        links=(),
        kind=span.kind,
        status=status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class AllowlistSpanExporter(SpanExporter):
    def __init__(self, inner: SpanExporter) -> None:
        self.inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self.inner.export([_scrub_span(span) for span in spans])

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)


class AllowlistLogExporter(LogRecordExporter):
    def __init__(self, inner: LogRecordExporter) -> None:
        self.inner = inner

    def export(self, batch: Sequence[ReadableLogRecord]) -> LogRecordExportResult:
        scrubbed = []
        for record in batch:
            clean = copy.copy(record.log_record)
            clean.attributes = keep(record.log_record.attributes, LOG_KEYS)
            clean.exception = None
            scrubbed.append(
                ReadableLogRecord(
                    log_record=clean,
                    resource=record.resource,
                    instrumentation_scope=record.instrumentation_scope,
                    limits=record.limits,
                )
            )
        return self.inner.export(scrubbed)

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)
