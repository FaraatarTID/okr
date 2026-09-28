from __future__ import annotations

from datetime import datetime, timezone
import importlib
import importlib.util
import json
import math
import secrets
from typing import cast

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
                "warmup_routes": ["/dashboard", "/daily"],
            },
        },
        "measurement": {
            "metric": "client_navigation_to_rendered_route_ms",
            "sample_count": 3,
            "samples": [
                {
                    "from_route": "/dashboard",
                    "to_route": "/daily",
                    "same_document_navigation": True,
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
                    "same_document_navigation": True,
                    "duration_ms": 115.0,
                    "requests": [
                        {
                            "sequence": 1,
                            "method": "GET",
                            "path": "/api/backend/v1/read/query",
                            "status": 200,
                            "duration_ms": 38.0,
                            "server_timing_ms": {
                                "app": 7.0,
                                "data": 4.0,
                                "bff-upstream": 27.0,
                            },
                        }
                    ],
                },
                {
                    "from_route": "/dashboard",
                    "to_route": "/daily",
                    "same_document_navigation": True,
                    "duration_ms": 135.0,
                    "requests": [
                        {
                            "sequence": 1,
                            "method": "GET",
                            "path": "/api/backend/v1/read/query",
                            "status": 200,
                            "duration_ms": 45.0,
                            "server_timing_ms": {
                                "app": 8.0,
                                "data": 5.0,
                                "bff-upstream": 29.0,
                            },
                        }
                    ],
                },
            ],
            "summary_ms": {"p50": 125.0, "p95": 135.0},
            "server_timing_p50_ms": {"app": 8.0, "data": 5.0, "bff-upstream": 29.0},
        },
    }


def _as_dict(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _as_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def _first_sample(report: dict[str, object]) -> dict[str, object]:
    measurement = _as_dict(report["measurement"])
    return _as_dict(_as_list(measurement["samples"])[0])


def _first_request(report: dict[str, object]) -> dict[str, object]:
    first_sample = _first_sample(report)
    requests = _as_list(first_sample["requests"])
    return _as_dict(requests[0])


def test_valid_unscored_measurement_artifact_is_accepted() -> None:
    probe = _probe_module()

    probe.validate_measurement_artifact(_report())


def test_measurement_requires_forwarded_server_timing_for_read_queries() -> None:
    probe = _probe_module()
    report = _report()
    measurement = _as_dict(report["measurement"])
    for sample in _as_list(measurement["samples"]):
        for request in _as_list(_as_dict(sample)["requests"]):
            _as_dict(request)["server_timing_ms"] = {}
    measurement["server_timing_p50_ms"] = {}

    with pytest.raises(probe.MeasurementValidationError, match="server.timing"):
        probe.validate_measurement_artifact(report)


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
            lambda report: _first_request(report).__setitem__(
                "path", "/api/read?token=do-not-record"
            ),
            "path",
        ),
        (
            lambda report: _first_request(report).__setitem__(
                "path", "/api/backend/v1/users/alice"
            ),
            "path",
        ),
        (
            lambda report: _first_request(report).__setitem__(
                "path", "/api/backend/v1/users/alice%40example.test"
            ),
            "path",
        ),
        (
            lambda report: report["measurement"]["samples"][0].__setitem__(
                "same_document_navigation", False
            ),
            "same-document",
        ),
        (
            lambda report: report["conditions"]["cache"].__setitem__(
                "warmup_routes", ["/dashboard"]
            ),
            "warmup_routes",
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


def test_request_path_sanitizer_drops_query_and_redacts_identifiers() -> None:
    probe = _probe_module()

    assert (
        probe._sanitize_request_path(
            "https://pre-release.example.test/api/backend/v1/jobs/123?token=secret"
        )
        == "/api/backend/v1/jobs/{id}"
    )
    assert (
        probe._sanitize_request_path(
            "https://pre-release.example.test/api/backend/v1/users/9da8735f-a142-4bb3-9205-611591f79111"
        )
        == "/api/backend/v1/users/{id}"
    )
    assert (
        probe._sanitize_request_path(
            "https://pre-release.example.test/api/backend/v1/users/alice"
        )
        == "/api/backend/v1/users/{id}"
    )
    assert (
        probe._sanitize_request_path(
            "https://pre-release.example.test/api/backend/v1/users/alice%40example.test"
        )
        == "/api/backend/v1/users/{id}"
    )
    assert (
        probe._sanitize_request_path(
            "https://pre-release.example.test/api/backend/v1/read/query/alice"
        )
        is None
    )
    assert (
        probe._sanitize_request_path(
            "https://pre-release.example.test/internal/alice?token=private"
        )
        is None
    )


def test_client_route_warmup_requires_same_document(monkeypatch) -> None:
    probe = _probe_module()
    monkeypatch.setattr(probe, "_rendered_route", lambda page, route: None)

    class FakePage:
        def __init__(self, origins: list[float]) -> None:
            self.origins = iter(origins)
            self.clicked = ""
            self.waited_for = ""

        def evaluate(self, expression: str) -> float:
            assert expression == "performance.timeOrigin"
            return next(self.origins)

        def get_by_role(self, role: str, *, name: str, exact: bool):
            assert role == "button" and exact is True
            self.clicked = name
            return self

        def click(self) -> None:
            pass

        def wait_for_url(self, pattern: str, *, timeout: int) -> None:
            self.waited_for = pattern

    same_document = FakePage([100.0, 100.0])
    probe._navigate_client_side(same_document, "/daily")
    assert same_document.clicked == "Daily Report"
    assert same_document.waited_for == "**/daily"

    replaced_document = FakePage([100.0, 200.0])
    with pytest.raises(probe.MeasurementValidationError, match="same browser document"):
        probe._navigate_client_side(replaced_document, "/daily")


def test_summary_builder_does_not_score_measured_timing() -> None:
    probe = _probe_module()
    report = _report()

    assert report["score_status"] == "unscored"
    probe.validate_measurement_artifact(report)


def test_utc_timestamp_fixture_is_timezone_aware() -> None:
    timestamp = _report()["captured_at_utc"]
    assert isinstance(timestamp, str)
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    assert parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(
        parsed
    )


def test_cli_writes_a_validated_unscored_report_without_serializing_credentials(
    tmp_path, monkeypatch
) -> None:
    probe = _probe_module()
    output = tmp_path / "frontend-performance.json"
    username = "synthetic-user"
    password = "synthetic-secret"
    monkeypatch.setenv("PROBE_USER", username)
    monkeypatch.setenv("PROBE_PASSWORD", password)
    captured: dict[str, object] = {}

    def fake_capture(**kwargs):
        captured.update(kwargs)
        return _report()

    monkeypatch.setattr(probe, "capture_measurement_report", fake_capture)
    result = probe.main(
        [
            "--base-url",
            "https://pre-release.example.test",
            "--username-env",
            "PROBE_USER",
            "--password-env",
            "PROBE_PASSWORD",
            "--build-id",
            "darkube-web-build-123",
            "--commit-sha",
            "a" * 40,
            "--data-access-mode",
            "database",
            "--output",
            str(output),
        ]
    )

    serialized = output.read_text(encoding="utf-8")
    assert result == 0
    assert captured["username"] == username
    assert captured["password"] == password
    assert json.loads(serialized)["score_status"] == "unscored"
    assert username not in serialized
    assert password not in serialized
    probe.validate_measurement_artifact(json.loads(serialized))


def test_cli_rejects_missing_environment_credentials_without_echoing_values(
    tmp_path, monkeypatch, capsys
) -> None:
    probe = _probe_module()
    monkeypatch.delenv("MISSING_PROBE_USER", raising=False)
    password = secrets.token_urlsafe(24)
    monkeypatch.setenv("PROBE_PASSWORD", password)

    result = probe.main(
        [
            "--base-url",
            "https://pre-release.example.test",
            "--username-env",
            "MISSING_PROBE_USER",
            "--password-env",
            "PROBE_PASSWORD",
            "--build-id",
            "darkube-web-build-123",
            "--commit-sha",
            "a" * 40,
            "--data-access-mode",
            "database",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert result != 0
    error_output = capsys.readouterr().err
    assert "MISSING_PROBE_USER" in error_output
    assert password not in error_output
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://pre-release.example.test/path",
        "https://user:password@pre-release.example.test",
        "https://pre-release.example.test/?token=secret",
    ],
)
def test_cli_rejects_non_origin_base_urls(base_url: str, tmp_path, monkeypatch) -> None:
    probe = _probe_module()
    monkeypatch.setenv("PROBE_USER", "synthetic-user")
    monkeypatch.setenv("PROBE_PASSWORD", "synthetic-password")
    monkeypatch.setattr(
        probe,
        "capture_measurement_report",
        lambda **kwargs: pytest.fail("invalid URL must fail before browser startup"),
        raising=False,
    )

    result = probe.main(
        [
            "--base-url",
            base_url,
            "--username-env",
            "PROBE_USER",
            "--password-env",
            "PROBE_PASSWORD",
            "--build-id",
            "darkube-web-build-123",
            "--commit-sha",
            "a" * 40,
            "--data-access-mode",
            "database",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert result != 0
    assert not (tmp_path / "report.json").exists()
