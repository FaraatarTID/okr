#!/usr/bin/env python3
"""Offline validation for trace export configuration; never sends telemetry."""
from __future__ import annotations
import os
import sys
from urllib.parse import urlparse

disabled = os.getenv("OTEL_SDK_DISABLED") == "true"
endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
queue = os.getenv("OTEL_BSP_MAX_QUEUE_SIZE", "2048")
if disabled or not endpoint:
    print("observability readiness: tracing disabled (valid for tests)")
    raise SystemExit(0)
if protocol != "http/protobuf" or urlparse(endpoint).scheme not in {"http", "https"}:
    print("invalid OTLP HTTP/protobuf endpoint or protocol", file=sys.stderr); raise SystemExit(1)
try:
    assert 1 <= int(queue) <= 65536
except (AssertionError, ValueError):
    print("OTEL_BSP_MAX_QUEUE_SIZE must be 1..65536", file=sys.stderr); raise SystemExit(1)
print("observability readiness: configuration valid (no export attempted)")
