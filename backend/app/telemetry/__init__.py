"""OpenTelemetry for the optional local telemetry stack (#56).

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set and OTEL_SDK_DISABLED is not
"true". The rest of the app reaches this package only through create_app.
"""

from __future__ import annotations

import os

from fastapi import FastAPI


def telemetry_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return False
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_telemetry(app: FastAPI) -> None:
    if not telemetry_enabled():
        return

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create()
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls="/health,/ready",
        exclude_spans=["receive", "send"],
    )
