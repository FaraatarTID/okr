"""Best-effort OpenTelemetry setup. Telemetry must never fail application traffic.

Only protocol, method and FastAPI route templates are exported; SDK instrumentation
is configured with SQL comment/query capture disabled so values and SQL text do not
leave the process.
"""
from __future__ import annotations

import logging
import os
from typing import Any

_configured = False
logger = logging.getLogger(__name__)


def telemetry_enabled() -> bool:
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")) and os.getenv("OTEL_SDK_DISABLED") != "true"


def configure_telemetry(app: Any | None = None, engine: Any | None = None) -> bool:
    """Install bounded OTLP HTTP tracing and supported framework integrations.

    Missing optional packages or unreachable collectors are intentionally non-fatal.
    OTEL_BSP_MAX_QUEUE_SIZE bounds memory use; the SDK batches exports and flushes at
    FastAPI shutdown. HTTP trace context remains HTTP-only and is never put in SQL.
    """
    global _configured
    if not telemetry_enabled():
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.info("OpenTelemetry packages are unavailable; tracing disabled")
        return False
    try:
        if not _configured:
            resource = Resource.create({
                "service.name": os.getenv("OTEL_SERVICE_NAME", "okr-backend"),
                "deployment.environment.name": os.getenv("OKR_RUNTIME_ENV", "development"),
                "service.version": os.getenv("OKR_RELEASE", "unknown"),
            })
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            trace.set_tracer_provider(provider)
            RequestsInstrumentor().instrument()
            HTTPXClientInstrumentor().instrument()
            Psycopg2Instrumentor().instrument()
            _configured = True
        if app is not None:
            FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz")
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine, enable_commenter=False)
        return True
    except Exception:
        logger.warning("OpenTelemetry initialization failed; tracing disabled", exc_info=True)
        return False


def shutdown_telemetry() -> None:
    try:
        from opentelemetry import trace
        trace.get_tracer_provider().shutdown()
    except Exception:
        pass


def trace_log_fields() -> dict[str, str]:
    try:
        from opentelemetry import trace
        context = trace.get_current_span().get_span_context()
        if context and context.is_valid:
            return {"trace_id": format(context.trace_id, "032x"), "span_id": format(context.span_id, "016x")}
    except Exception:
        pass
    return {}
