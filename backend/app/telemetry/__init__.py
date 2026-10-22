"""OpenTelemetry for the optional local telemetry stack (#56).

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set and OTEL_SDK_DISABLED is not
"true". The rest of the app reaches this package only through create_app.
"""

from __future__ import annotations

import logging
import os
import sys

from fastapi import FastAPI


def telemetry_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_telemetry(app: FastAPI) -> None:
    if not telemetry_enabled():
        return

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from app.telemetry.json_log import JsonLineFormatter
    from app.telemetry.request_log import REQUEST_LOGGER, RequestLogMiddleware

    resource = Resource.create()
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    request_logger = logging.getLogger(REQUEST_LOGGER)
    request_logger.handlers.clear()  # ours alone; create_app may run more than once
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
        excluded_urls="/health,/ready",
        exclude_spans=["receive", "send"],
    )
