from __future__ import annotations

from datetime import datetime, timezone
import importlib
import importlib.util
import math

import pytest


def _probe_module():
    spec = importlib.util.find_spec("scripts.probe_frontend_budget")
    assert spec is not None, "live frontend budget report validator is not implemented"
    return importlib.import_module("scripts.probe_frontend_budget")


def _report() -> dict[str, object]:
    return {
        "schema_version": 1,
        "probe": "frontend-page-budget",
        "score_status": "unscored",
        "captured_at_utc": "2026-09-23T14:00:00Z",
        "build": {
            "commit_sha": "a" * 40,
            "build_id": "darkube-web-build-123",
        },
        "target": {"origin": "https://pre-release.example.test", "route": "/dashboard"},
        "conditions": {
            "browser": {
                "engine": "chromium",
                "version": "140.0.7339.0",
                "playwright_version": "1.60.0",
                "viewport": {"width": 1600, "height": 1000},
            },
            "stack_readiness": {
                "ready": True,
                "web_status": 200,
                "bff_status": 200,
                "authenticated_route_status": 200,
                "checked_at_utc": "2026-09-23T13:59:00Z",
            },
            "data_access_mode": "database",
            "cache": {
                "browser_http_cache": "warm",
                "application_resource_cache": "warm",
                "warmup_route": "/dashboard",
            },
        },
        "measurement": {
            "metric": "client_navigation_to_rendered_route_ms",
            "sample_count": 3,
            "samples": [
                {
                    "from_route": "/dashboard",
                    "to_route": "/daily",
                    "duration_ms": 125.0,
                    "requests": [
                        {
                            "sequence": 1,
                            "method": "GET",
                            "path": "/api/backend/v1/read/query",
                            "status": 200,
                            "duration_ms": 42.0,
                            "server_timing_ms": {
                                "app": 8.2,
                                "data": 5.3,
                                "bff-upstream": 30.1,
                            },
                        }
                    ],
                },
                {
                    "from_route": "/daily",
                    "to_route": "/dashboard",
                    "duration_ms": 115.0,
                    "requests": [
                        {
                            "sequence": 1,
                            "method": "GET",
                            "path": "/api/backend/v1/read/query",
                            "status": 200,
                            "duration_ms": 38.0,
                            "server_timing_ms": {"app": 7.0, "data": 4.0},
                        }
                    ],
                },
                {
                    "from_route": "/dashboard",
                    "to_route": "/daily",
                    "duration_ms": 135.0,
                    "requests": [
                        {
                            "sequence": 1,
                            "method": "GET",
                            "path": "/api/backend/v1/read/query",
                            "status": 200,
                            "duration_ms": 45.0,
                            "server_timing_ms": {},
                        }
                    ],
                },
            ],
            "summary_ms": {"p50": 125.0, "p95": 135.0},
            "server_timing_p50_ms": {"app": 7.6, "data": 4.65, "bff-upstream": 30.1},
        },
    }


def test_valid_unscored_measurement_artifact_is_accepted() -> None:
    probe = _probe_module()

    probe.validate_measurement_artifact(_report())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda report: report.pop("build"), "build"),
        (lambda report: report.__setitem__("score_status", "pass"), "score_status"),
        (
            lambda report: report["conditions"].__setitem__(
                "data_access_mode", "unknown"
            ),
            "data_access_mode",
        ),
        (
            lambda report: report["measurement"].__setitem__("sample_count", 0),
            "sample_count",
        ),
        (
            lambda report: report["measurement"]["samples"][0].__setitem__(
                "duration_ms", math.nan
            ),
            "duration_ms",
        ),
        (
            lambda report: report["measurement"]["samples"][0]["requests"][
                0
            ].__setitem__("path", "/api/read?token=do-not-record"),
            "path",
        ),
        (
            lambda report: report["conditions"]["stack_readiness"].__setitem__(
                "bff_status", 503
            ),
            "stack_readiness",
        ),
    ],
)
def test_invalid_or_sensitive_measurement_artifact_is_rejected(
    mutate, message: str
) -> None:
    probe = _probe_module()
    report = _report()
    mutate(report)

    with pytest.raises(probe.MeasurementValidationError, match=message):
        probe.validate_measurement_artifact(report)


def test_server_timing_parser_keeps_only_safe_finite_duration_metrics() -> None:
    probe = _probe_module()

    assert probe.parse_server_timing(
        "app;dur=8.25, data;dur=5, bff-upstream;dur=30.125, secret;dur=4, app;dur=NaN"
    ) == {"app": 8.25, "data": 5.0, "bff-upstream": 30.125}


def test_summary_builder_does_not_score_measured_timing() -> None:
    probe = _probe_module()
    report = _report()

    assert report["score_status"] == "unscored"
    probe.validate_measurement_artifact(report)


def test_utc_timestamp_fixture_is_timezone_aware() -> None:
    parsed = datetime.fromisoformat(_report()["captured_at_utc"].replace("Z", "+00:00"))

    assert parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(
        parsed
    )
