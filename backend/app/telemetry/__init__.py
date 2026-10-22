"""OpenTelemetry for the optional local telemetry stack (#56).

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set and OTEL_SDK_DISABLED is not
"true". The rest of the app reaches this package only through create_app.

Every exporter is wrapped by the allowlist in `allowlist.py`, so nothing but
the listed attribute keys leaves the process.
"""

from __future__ import annotations

import logging
import os
import sys

from fastapi import FastAPI
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import LogRecordExporter
from opentelemetry.sdk.metrics.export import MetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter

#: Only API requests are traced. The regex is matched against the full URL, so
#: this skips everything whose path does not start with /api/: the probes
#: (/health, /ready called every 30 s), the static frontend and its assets.
TRACED_URL_ONLY_API = r"^\w+://[^/]*/(?!api/)"


def telemetry_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_telemetry(
    app: FastAPI,
    *,
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
    log_exporter: LogRecordExporter | None = None,
) -> None:
    """Install tracing, metrics and the request log on `app`, if telemetry is on.

    The keyword arguments are a test seam: an injected exporter or reader
    replaces the OTLP one (and is exported synchronously). Whatever is used
    sits behind the allowlist.
    """
    if not telemetry_enabled():
        return

    # The stable HTTP names (http.server.request.duration, url.path, ...) are what
    # the dashboard and the allowlist expect. The instrumentation reads this
    # once, at its first use, so a default set here holds for the whole process.
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk._logs import LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, SimpleLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    from app.telemetry.allowlist import (
        AllowlistLogExporter,
        AllowlistSpanExporter,
        metric_views,
        safe_resource,
    )
    from app.telemetry.json_log import JsonLineFormatter
    from app.telemetry.request_log import REQUEST_LOGGER, RequestLogMiddleware

    resource = safe_resource(Resource.create())

    tracer_provider = TracerProvider(resource=resource)
    if span_exporter is None:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(AllowlistSpanExporter(OTLPSpanExporter()))
        )
    else:
        tracer_provider.add_span_processor(
            SimpleSpanProcessor(AllowlistSpanExporter(span_exporter))
        )

    reader = metric_reader or PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader], views=metric_views())

    logger_provider = LoggerProvider(resource=resource)
    if log_exporter is None:
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(AllowlistLogExporter(OTLPLogExporter()))
        )
    else:
        logger_provider.add_log_record_processor(
            SimpleLogRecordProcessor(AllowlistLogExporter(log_exporter))
        )

    request_logger = logging.getLogger(REQUEST_LOGGER)
    request_logger.handlers.clear()  # ours alone; create_app may run more than once
    # Only this logger gets the handler, never the root logger: anything else
    # logged in the process stays out of telemetry.
    request_logger.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    if os.environ.get("LOG_FORMAT", "").strip().lower() == "json":
        stdout_handler = logging.StreamHandler(sys.stdout)
        service = str(resource.attributes.get("service.name", "unknown"))
        stdout_handler.setFormatter(JsonLineFormatter(service))
        request_logger.addHandler(stdout_handler)
    request_logger.setLevel(logging.INFO)
    request_logger.propagate = False

    app.add_middleware(RequestLogMiddleware)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls=TRACED_URL_ONLY_API,
        exclude_spans=["receive", "send"],
    )
