from __future__ import annotations

from src import telemetry


def test_exporter_disabled_is_non_fatal(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    assert telemetry.configure_telemetry() is False
    assert telemetry.trace_log_fields() == {}


def test_no_endpoint_disables_exporter(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    assert telemetry.telemetry_enabled() is False
