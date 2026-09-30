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
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


SCHEMA_VERSION = 1
PROBE_NAME = "frontend-page-budget"
SCORE_STATUS = "unscored"
METRIC_NAME = "client_navigation_to_rendered_route_ms"
READ_QUERY_PATH = "/api/backend/v1/read/query"
REQUIRED_READ_SERVER_TIMING = {"app", "data", "bff-upstream"}
VIEWPORT = {"width": 1600, "height": 1000}
DATA_ACCESS_MODES = {"database"}
ALLOWED_SERVER_TIMING = {"app", "data", "bff-upstream"}
_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_SAFE_REQUEST_PATHS = {
    "/",
    "/login",
    "/dashboard",
    "/daily",
    "/favicon.ico",
    "/api/healthz",
    "/api/session/login",
    "/api/session/me",
    "/api/session/logout",
    "/api/backend/v1/read/query",
    "/api/backend/v1/read/atlas/snapshot",
    "/api/backend/v1/read/leadership/metrics",
}
_DYNAMIC_REQUEST_PATHS = (
    re.compile(
        r"/api/backend/v1/(?:users|teams|cycles|jobs|experiments|alignments|work-logs|objective-alignment-links)/\{id\}(?:/(?:cancel|retry|close|reset-password|experiment-outcomes))?"
    ),
    re.compile(r"/api/backend/v1/nodes/(?:goal|objective|key_result|task)/\{id\}"),
)
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


def _safe_request_path(value: object, field: str) -> str:
    """Accept only known routes or routes with explicit redacted ID slots."""
    path = _safe_path(value, field)
    if "%" in path:
        _fail(field, "must not contain percent-encoded data")
    if (
        path in _SAFE_REQUEST_PATHS
        or path == "/_next/static/{asset}"
        or path == "/_next/image"
    ):
        return path
    if any(pattern.fullmatch(path) for pattern in _DYNAMIC_REQUEST_PATHS):
        return path
    _fail(field, "is not a recognized sanitized request path")


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
        _fail("data_access_mode", "must identify database")
    cache = _mapping(
        conditions["cache"],
        "conditions.cache",
        {"browser_http_cache", "application_resource_cache", "warmup_routes"},
    )
    if (
        cache["browser_http_cache"] != "warm"
        or cache["application_resource_cache"] != "warm"
    ):
        _fail("conditions.cache", "must record both caches as warm")
    warmup_routes = cache["warmup_routes"]
    if warmup_routes != ["/dashboard", "/daily"]:
        _fail("conditions.cache.warmup_routes", "must include both rendered routes")

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
    has_correlated_read_request = False
    for index, raw_sample in enumerate(samples):
        field = f"samples[{index}]"
        sample = _mapping(
            raw_sample,
            field,
            {
                "from_route",
                "to_route",
                "duration_ms",
                "requests",
                "same_document_navigation",
            },
        )
        _safe_path(sample["from_route"], f"{field}.from_route", allowed_routes)
        _safe_path(sample["to_route"], f"{field}.to_route", allowed_routes)
        if sample["same_document_navigation"] is not True:
            _fail(
                f"{field}.same_document_navigation",
                "must prove same-document navigation",
            )
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
            path = _safe_request_path(request["path"], f"{request_field}.path")
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
            if path == READ_QUERY_PATH:
                missing_timing = REQUIRED_READ_SERVER_TIMING.difference(timing)
                if missing_timing:
                    _fail(
                        f"{request_field}.server_timing_ms",
                        "read query is missing required app, data, and bff-upstream timing",
                    )
                has_correlated_read_request = True
        if sequences != list(range(1, len(sequences) + 1)):
            _fail(f"{field}.requests", "must preserve contiguous request order")

    if not has_correlated_read_request:
        _fail(
            "measurement.requests",
            "must include a read query with app, data, and bff-upstream Server-Timing",
        )

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


def _readiness_status(url: str) -> int:
    """Read one unauthenticated readiness endpoint with a bounded timeout."""
    try:
        with urlopen(url, timeout=15) as response:  # nosec B310 - validated origin
            return int(response.status)
    except HTTPError as error:
        return int(error.code)
    except (URLError, OSError, TimeoutError) as error:
        raise MeasurementValidationError(
            "stack readiness could not be checked"
        ) from error


def _sanitize_request_path(raw_url: str) -> str | None:
    """Return a recognized route with query data and arbitrary IDs removed."""
    parsed = urlsplit(raw_url)
    path = parsed.path or "/"
    if not path.startswith("/") or path.startswith("//"):
        return None
    if path in _SAFE_REQUEST_PATHS or path == "/_next/image":
        return path
    if path.startswith("/_next/static/"):
        return "/_next/static/{asset}"
    dynamic_route = re.fullmatch(
        r"(/api/backend/v1/(?:users|teams|cycles|jobs|experiments|alignments|work-logs|objective-alignment-links))/([^/]+)(/(?:cancel|retry|close|reset-password|experiment-outcomes))?",
        path,
    )
    if dynamic_route is not None:
        sanitized = f"{dynamic_route.group(1)}/{{id}}{dynamic_route.group(3) or ''}"
        return sanitized if _is_safe_request_path(sanitized) else None
    node_route = re.fullmatch(
        r"(/api/backend/v1/nodes/(?:goal|objective|key_result|task))/([^/]+)",
        path,
    )
    if node_route is not None:
        return f"{node_route.group(1)}/{{id}}"
    return None


def _is_safe_request_path(path: str) -> bool:
    return (
        path in _SAFE_REQUEST_PATHS
        or path
        in {
            "/_next/static/{asset}",
            "/_next/image",
        }
        or any(pattern.fullmatch(path) for pattern in _DYNAMIC_REQUEST_PATHS)
    )


def _rendered_route(page: Any, route: str) -> None:
    """Wait for a route's user-visible content, not just a URL transition."""
    if route == "/dashboard":
        page.get_by_role("heading", name="Dashboard Workspace", exact=True).wait_for(
            state="visible", timeout=90_000
        )
        page.get_by_text("Execution Completion", exact=True).wait_for(
            state="visible", timeout=90_000
        )
    elif route == "/daily":
        page.locator("p.kicker").filter(has_text="Daily Report").first.wait_for(
            state="visible", timeout=90_000
        )
        page.get_by_role("heading", name="Time Distribution", exact=True).wait_for(
            state="visible", timeout=90_000
        )
    else:
        _fail("target.route", "is not an approved measured route")


def _navigate_client_side(page: Any, route: str) -> None:
    """Visit and render a shell route without replacing the browser document."""
    before = float(page.evaluate("performance.timeOrigin"))
    label = "Daily Report" if route == "/daily" else "Dashboard"
    page.get_by_role("button", name=label, exact=True).click()
    page.wait_for_url(f"**{route}", timeout=90_000)
    _rendered_route(page, route)
    after = float(page.evaluate("performance.timeOrigin"))
    if before != after:
        _fail("navigation", "route warmup must remain in the same browser document")


def capture_measurement_report(
    *,
    base_url: str,
    username: str,
    password: str,
    build_id: str,
    commit_sha: str,
    data_access_mode: str,
) -> dict[str, Any]:
    """Capture a bounded authenticated warm-navigation trace with Chromium."""
    origin = _safe_origin(base_url)
    _string(build_id, "build.build_id", _SAFE_ID_RE)
    _string(commit_sha, "build.commit_sha", _SHA_RE)
    if data_access_mode not in DATA_ACCESS_MODES:
        _fail("data_access_mode", "must identify database")
    _string(username, "username")
    _string(password, "password")

    checked_at = (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    web_status = _readiness_status(f"{origin}/login")
    bff_status = _readiness_status(f"{origin}/api/healthz")
    if web_status != 200 or bff_status != 200:
        _fail("stack_readiness", "web and BFF readiness endpoints must return HTTP 200")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise MeasurementValidationError(
            "Playwright is required to capture the browser measurement"
        ) from error

    samples: list[dict[str, Any]] = []
    captured_browser_version = ""
    authenticated_route_status = 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport=VIEWPORT)
                page = context.new_page()
                page.goto(
                    f"{origin}/login", wait_until="domcontentloaded", timeout=90_000
                )
                page.locator("#username").fill(username)
                page.locator("#password").fill(password)
                page.get_by_role("button", name="Sign in", exact=True).click()
                page.get_by_role("button", name="Sign out", exact=True).wait_for(
                    state="visible", timeout=90_000
                )
                route_response = page.goto(
                    f"{origin}/dashboard", wait_until="domcontentloaded", timeout=90_000
                )
                authenticated_route_status = (
                    int(route_response.status) if route_response is not None else 0
                )
                if authenticated_route_status != 200:
                    _fail(
                        "stack_readiness",
                        "authenticated dashboard did not return HTTP 200",
                    )
                _rendered_route(page, "/dashboard")

                # Warm both route views in the same mounted shell before timing.
                # This gives the browser asset cache and shared resource cache a
                # reproducible warm state while preserving the client document.
                _navigate_client_side(page, "/daily")
                _navigate_client_side(page, "/dashboard")

                captured_browser_version = str(browser.version)
                for sample_index in range(5):
                    source = "/dashboard" if sample_index % 2 == 0 else "/daily"
                    target = "/daily" if source == "/dashboard" else "/dashboard"
                    if source != (urlsplit(page.url).path or "/"):
                        _fail(
                            "measurement", "sample source route is not the warmed route"
                        )

                    requests: list[dict[str, Any]] = []
                    pending: dict[int, dict[str, Any]] = {}
                    document_requests = 0

                    def on_request(request: Any) -> None:
                        nonlocal document_requests
                        if str(request.resource_type) == "document":
                            document_requests += 1
                        parsed = urlsplit(str(request.url))
                        if f"{parsed.scheme}://{parsed.netloc}" != origin:
                            return
                        path = _sanitize_request_path(str(request.url))
                        method = str(request.method).upper()
                        if path is None or method not in {
                            "GET",
                            "HEAD",
                            "POST",
                            "PUT",
                            "PATCH",
                            "DELETE",
                        }:
                            return
                        record: dict[str, Any] = {
                            "sequence": len(requests) + 1,
                            "method": method,
                            "path": path,
                            "status": 0,
                            "duration_ms": 0.0,
                            "server_timing_ms": {},
                        }
                        requests.append(record)
                        pending[id(request)] = {
                            "record": record,
                            "started": time.perf_counter(),
                        }

                    def on_request_finished(request: Any) -> None:
                        trace = pending.pop(id(request), None)
                        if trace is None:
                            return
                        response = request.response()
                        if response is None:
                            return
                        record = trace["record"]
                        record["status"] = int(response.status)
                        record["duration_ms"] = round(
                            (time.perf_counter() - trace["started"]) * 1000, 3
                        )
                        record["server_timing_ms"] = parse_server_timing(
                            response.headers.get("server-timing")
                        )

                    def on_request_failed(request: Any) -> None:
                        pending.pop(id(request), None)

                    page.on("request", on_request)
                    page.on("requestfinished", on_request_finished)
                    page.on("requestfailed", on_request_failed)
                    time_origin_before = float(page.evaluate("performance.timeOrigin"))
                    started = time.perf_counter()
                    page.get_by_role(
                        "button",
                        name="Daily Report" if target == "/daily" else "Dashboard",
                        exact=True,
                    ).click()
                    page.wait_for_url(f"**{target}", timeout=90_000)
                    _rendered_route(page, target)
                    duration_ms = round((time.perf_counter() - started) * 1000, 3)
                    time_origin_after = float(page.evaluate("performance.timeOrigin"))
                    page.remove_listener("request", on_request)
                    page.remove_listener("requestfinished", on_request_finished)
                    page.remove_listener("requestfailed", on_request_failed)
                    if document_requests or time_origin_before != time_origin_after:
                        _fail(
                            "measurement.navigation",
                            "route transition replaced the browser document",
                        )
                    if pending or any(request["status"] == 0 for request in requests):
                        _fail(
                            "measurement.requests",
                            "a same-origin request did not complete",
                        )
                    if any(not 200 <= request["status"] < 400 for request in requests):
                        _fail(
                            "measurement.requests",
                            "a same-origin request was unsuccessful",
                        )
                    if not requests:
                        _fail(
                            "measurement.requests",
                            "no same-origin browser requests were measured",
                        )
                    samples.append(
                        {
                            "from_route": source,
                            "to_route": target,
                            "duration_ms": duration_ms,
                            "same_document_navigation": True,
                            "requests": requests,
                        }
                    )
                context.close()
            finally:
                browser.close()
    except MeasurementValidationError:
        raise
    except Exception as error:
        # Playwright's exception text can contain URLs and request details. Keep
        # the artifact/log message generic so response data and credentials do
        # not leak through an error path.
        raise MeasurementValidationError(
            "authenticated browser measurement did not complete"
        ) from error

    timing_summary, server_timing_summary = _expected_summary(
        [
            {
                "duration_ms": sample["duration_ms"],
                "requests": sample["requests"],
            }
            for sample in samples
        ]
    )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "probe": PROBE_NAME,
        "score_status": SCORE_STATUS,
        "captured_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "build": {"commit_sha": commit_sha, "build_id": build_id},
        "target": {"origin": origin, "route": "/dashboard"},
        "conditions": {
            "browser": {
                "engine": "chromium",
                "version": captured_browser_version,
                "playwright_version": importlib.metadata.version("playwright"),
                "viewport": dict(VIEWPORT),
            },
            "stack_readiness": {
                "ready": True,
                "web_status": web_status,
                "bff_status": bff_status,
                "authenticated_route_status": authenticated_route_status,
                "checked_at_utc": checked_at,
            },
            "data_access_mode": data_access_mode,
            "cache": {
                "browser_http_cache": "warm",
                "application_resource_cache": "warm",
                "warmup_routes": ["/dashboard", "/daily"],
            },
        },
        "measurement": {
            "metric": METRIC_NAME,
            "sample_count": len(samples),
            "samples": samples,
            "summary_ms": timing_summary,
            "server_timing_p50_ms": server_timing_summary,
        },
    }
    validate_measurement_artifact(report)
    return report


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username-env", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--data-access-mode", required=True, choices=sorted(DATA_ACCESS_MODES)
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the protected-stack probe and write its sanitized report."""
    args = _argument_parser().parse_args(argv)
    try:
        origin = _safe_origin(args.base_url)
        _string(args.build_id, "build.build_id", _SAFE_ID_RE)
        _string(args.commit_sha, "build.commit_sha", _SHA_RE)
        for env_name in (args.username_env, args.password_env):
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name) is None:
                _fail("credential environment variable", "name is invalid")
        username = os.environ.get(args.username_env)
        password = os.environ.get(args.password_env)
        if not username:
            _fail("credential environment variable", f"{args.username_env} is missing")
        if not password:
            _fail("credential environment variable", f"{args.password_env} is missing")
        report = capture_measurement_report(
            base_url=origin,
            username=username,
            password=password,
            build_id=args.build_id,
            commit_sha=args.commit_sha,
            data_access_mode=args.data_access_mode,
        )
        validate_measurement_artifact(report)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, MeasurementValidationError, ValueError) as error:
        print(f"frontend performance probe failed: {error}", file=sys.stderr)
        return 1
    print("frontend performance report written (score_status=unscored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
