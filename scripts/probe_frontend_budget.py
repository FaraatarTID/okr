"""Capture an authenticated warmed-browser SPA navigation measurement.

Credentials and deployment facts are read from protected environment variables,
never command-line arguments. The output is sanitized JSON evidence. It reports
timings but deliberately has no pass/fail performance threshold.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any, NoReturn
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
PROBE_NAME = "frontend-page-budget"
SCORE_STATUS = "unscored"
METRIC_NAME = "client_navigation_to_rendered_route_ms"
VIEWPORT = {"width": 1600, "height": 1000}
DATA_ACCESS_MODES = {"database", "supabase_api"}
ALLOWED_SERVER_TIMING = {"app", "data", "bff-upstream"}
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_SERVER_TIMING_RE = re.compile(
    r"^\s*(?P<name>[a-z][a-z0-9_-]*)\s*;\s*dur\s*=\s*"
    r"(?P<duration>[0-9]+(?:\.[0-9]+)?)\s*(?:;.*)?$",
    re.IGNORECASE,
)


class MeasurementValidationError(ValueError):
    """Raised when a frontend budget report is incomplete or unsafe."""


def parse_server_timing(value: str | None) -> dict[str, float]:
    """Keep only known duration metrics; discard descriptions and unknown names."""
    result: dict[str, float] = {}
    for part in str(value or "").split(","):
        match = _SERVER_TIMING_RE.fullmatch(part)
        if match is None:
            continue
        name = match.group("name").lower()
        if name not in ALLOWED_SERVER_TIMING:
            continue
        duration = float(match.group("duration"))
        if math.isfinite(duration) and duration >= 0:
            result[name] = duration
    return result


def _fail(field: str, message: str) -> NoReturn:
    raise MeasurementValidationError(f"{field} {message}")


def _mapping(value: object, field: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(field, "must be an object")
    if set(value) != keys:
        _fail(field, f"must contain exactly: {', '.join(sorted(keys))}")
    return value


def _string(value: object, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "must be a non-empty string")
    normalized = value.strip()
    if any(ord(character) < 32 for character in normalized):
        _fail(field, "contains a control character")
    if pattern is not None and pattern.fullmatch(normalized) is None:
        _fail(field, "has an invalid format")
    return normalized


def _number(value: object, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(field, "must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        _fail(field, "must be a finite non-negative number")
    return result


def _utc_timestamp(value: object, field: str) -> str:
    text = _string(value, field)
    if not text.endswith("Z"):
        _fail(field, "must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise MeasurementValidationError(
            f"{field} is not a valid UTC timestamp"
        ) from error
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(field, "must be UTC")
    return text


def _safe_origin(value: object) -> str:
    origin = _string(value, "target.origin")
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        _fail("target.origin", "must be an origin without credentials, path, or query")
    return f"{parsed.scheme}://{parsed.netloc}"


def _safe_path(value: object, field: str, allowed: set[str] | None = None) -> str:
    path = _string(value, field)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or "?" in path
        or "#" in path
        or "\\" in path
    ):
        _fail(field, "must be a path without query or fragment")
    if allowed is not None and path not in allowed:
        _fail(field, "is not an approved measured route")
    return path


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def _expected_summary(
    samples: list[Mapping[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    durations = [
        _number(sample.get("duration_ms"), "duration_ms", positive=True)
        for sample in samples
    ]
    summary = {
        "p50": round(statistics.median(durations), 3),
        "p95": _percentile(durations, 0.95),
    }
    timing_values: dict[str, list[float]] = {}
    for sample in samples:
        requests = sample.get("requests")
        if isinstance(requests, list):
            for request in requests:
                if isinstance(request, Mapping):
                    timing = request.get("server_timing_ms")
                    if isinstance(timing, Mapping):
                        for name, duration in timing.items():
                            timing_values.setdefault(str(name), []).append(
                                _number(duration, f"server_timing_ms.{name}")
                            )
    timing_summary = {
        name: round(statistics.median(values), 3)
        for name, values in sorted(timing_values.items())
    }
    return summary, timing_summary


def validate_measurement_artifact(payload: object) -> None:
    """Validate the safe, deliberately unscored release measurement schema."""
    report = _mapping(
        payload,
        "report",
        {
            "schema_version",
            "probe",
            "score_status",
            "captured_at_utc",
            "build",
            "target",
            "conditions",
            "measurement",
        },
    )
    if report["schema_version"] != SCHEMA_VERSION:
        _fail("schema_version", "is unsupported")
    if report["probe"] != PROBE_NAME:
        _fail("probe", "is invalid")
    if report["score_status"] != SCORE_STATUS:
        _fail("score_status", "must remain unscored until an owner approves a target")
    _utc_timestamp(report["captured_at_utc"], "captured_at_utc")

    build = _mapping(report["build"], "build", {"commit_sha", "build_id"})
    _string(build["commit_sha"], "build.commit_sha", _SHA_RE)
    _string(build["build_id"], "build.build_id", _SAFE_ID_RE)

    target = _mapping(report["target"], "target", {"origin", "route"})
    _safe_origin(target["origin"])
    _safe_path(target["route"], "target.route", {"/dashboard"})

    conditions = _mapping(
        report["conditions"],
        "conditions",
        {"browser", "stack_readiness", "data_access_mode", "cache"},
    )
    browser = _mapping(
        conditions["browser"],
        "conditions.browser",
        {"engine", "version", "playwright_version", "viewport"},
    )
    if browser["engine"] != "chromium":
        _fail("conditions.browser.engine", "must be chromium")
    _string(browser["version"], "conditions.browser.version")
    _string(browser["playwright_version"], "conditions.browser.playwright_version")
    viewport = _mapping(
        browser["viewport"], "conditions.browser.viewport", {"width", "height"}
    )
    if dict(viewport) != VIEWPORT:
        _fail("conditions.browser.viewport", "does not match the pinned viewport")

    readiness = _mapping(
        conditions["stack_readiness"],
        "conditions.stack_readiness",
        {
            "ready",
            "web_status",
            "bff_status",
            "authenticated_route_status",
            "checked_at_utc",
        },
    )
    if readiness["ready"] is not True or any(
        readiness[name] != 200
        for name in ("web_status", "bff_status", "authenticated_route_status")
    ):
        _fail(
            "stack_readiness", "must prove web, BFF, and authenticated route readiness"
        )
    _utc_timestamp(readiness["checked_at_utc"], "stack_readiness.checked_at_utc")

    if conditions["data_access_mode"] not in DATA_ACCESS_MODES:
        _fail("data_access_mode", "must identify database or supabase_api")
    cache = _mapping(
        conditions["cache"],
        "conditions.cache",
        {"browser_http_cache", "application_resource_cache", "warmup_route"},
    )
    if (
        cache["browser_http_cache"] != "warm"
        or cache["application_resource_cache"] != "warm"
    ):
        _fail("conditions.cache", "must record both caches as warm")
    _safe_path(cache["warmup_route"], "conditions.cache.warmup_route", {"/dashboard"})

    measurement = _mapping(
        report["measurement"],
        "measurement",
        {"metric", "sample_count", "samples", "summary_ms", "server_timing_p50_ms"},
    )
    if measurement["metric"] != METRIC_NAME:
        _fail("measurement.metric", "is unsupported")
    samples = measurement["samples"]
    if not isinstance(samples, list) or not samples:
        _fail("measurement.samples", "must contain at least one sample")
    if measurement["sample_count"] != len(samples):
        _fail("sample_count", "must equal the number of samples")
    allowed_routes = {"/dashboard", "/daily"}
    for index, raw_sample in enumerate(samples):
        field = f"samples[{index}]"
        sample = _mapping(
            raw_sample,
            field,
            {"from_route", "to_route", "duration_ms", "requests"},
        )
        _safe_path(sample["from_route"], f"{field}.from_route", allowed_routes)
        _safe_path(sample["to_route"], f"{field}.to_route", allowed_routes)
        _number(sample["duration_ms"], f"{field}.duration_ms", positive=True)
        requests = sample["requests"]
        if not isinstance(requests, list) or not requests:
            _fail(f"{field}.requests", "must contain measured browser requests")
        sequences: list[int] = []
        for request_index, raw_request in enumerate(requests):
            request_field = f"{field}.requests[{request_index}]"
            request = _mapping(
                raw_request,
                request_field,
                {
                    "sequence",
                    "method",
                    "path",
                    "status",
                    "duration_ms",
                    "server_timing_ms",
                },
            )
            sequence = request["sequence"]
            if (
                isinstance(sequence, bool)
                or not isinstance(sequence, int)
                or sequence < 1
            ):
                _fail(f"{request_field}.sequence", "must be a positive integer")
            sequences.append(sequence)
            method = _string(request["method"], f"{request_field}.method")
            if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
                _fail(f"{request_field}.method", "is invalid")
            _safe_path(request["path"], f"{request_field}.path")
            status = request["status"]
            if (
                isinstance(status, bool)
                or not isinstance(status, int)
                or not 200 <= status < 400
            ):
                _fail(f"{request_field}.status", "must be a successful HTTP status")
            _number(request["duration_ms"], f"{request_field}.duration_ms")
            timing = _mapping(
                request["server_timing_ms"],
                f"{request_field}.server_timing_ms",
                set(request["server_timing_ms"])
                if isinstance(request["server_timing_ms"], Mapping)
                else set(),
            )
            if not set(timing).issubset(ALLOWED_SERVER_TIMING):
                _fail(f"{request_field}.server_timing_ms", "contains an unknown metric")
            for name, duration in timing.items():
                _number(duration, f"{request_field}.server_timing_ms.{name}")
        if sequences != list(range(1, len(sequences) + 1)):
            _fail(f"{field}.requests", "must preserve contiguous request order")

    expected_summary, expected_timing = _expected_summary(samples)
    summary = _mapping(
        measurement["summary_ms"], "measurement.summary_ms", {"p50", "p95"}
    )
    for name, expected in expected_summary.items():
        if _number(summary[name], f"measurement.summary_ms.{name}") != expected:
            _fail("measurement.summary_ms", "does not match raw samples")
    timing_summary = measurement["server_timing_p50_ms"]
    if not isinstance(timing_summary, Mapping):
        _fail("measurement.server_timing_p50_ms", "must be an object")
    if set(timing_summary) != set(expected_timing):
        _fail("measurement.server_timing_p50_ms", "does not match raw samples")
    for name, expected in expected_timing.items():
        if (
            _number(timing_summary[name], f"measurement.server_timing_p50_ms.{name}")
            != expected
        ):
            _fail("measurement.server_timing_p50_ms", "does not match raw samples")
