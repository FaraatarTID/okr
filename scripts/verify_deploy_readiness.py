#!/usr/bin/env python3
"""Verify post-deploy service readiness for backend, BFF, and frontend."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable


def _run_command(
    args: list[str],
    cwd: Path | None = None,
) -> tuple[int, str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return int(completed.returncode), output.strip()


def _http_json(url: str, timeout_seconds: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 0) or 0)
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return False, f"request failed: {exc}"

    if status < 200 or status >= 300:
        return False, f"HTTP {status}"

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return True, f"HTTP {status} (non-json response)"

    if not isinstance(payload, dict):
        return False, f"HTTP {status} (non-object JSON response)"

    if payload.get("status") != "ok":
        return False, f"health status is '{payload.get('status')}'"

    return True, f"status=ok payload_keys={sorted(payload.keys())}"


def _http_text(url: str, timeout_seconds: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 0) or 0)
            body = response.read(120).decode("utf-8", errors="replace")
    except Exception as exc:
        return False, f"request failed: {exc}"

    if status < 200 or status >= 300:
        return False, f"HTTP {status}"

    if not body:
        return True, "HTTP 2xx (empty response)"
    if "doctype" in body.lower():
        return True, "HTML payload looks healthy"
    return True, f"HTTP {status} (text response)"


def _poll_until_ready(
    label: str,
    checker: Callable[[], tuple[bool, str]],
    timeout_seconds: int,
    interval_seconds: float,
) -> bool:
    deadline = time.monotonic() + float(timeout_seconds)
    while True:
        ok, detail = checker()
        if ok:
            print(f"[PASS] {label}: {detail}")
            return True
        if time.monotonic() >= deadline:
            print(f"[FAIL] {label}: {detail}")
            return False
        print(f"[WAIT] {label}: {detail}")
        time.sleep(interval_seconds)


def _check_compose_services(
    compose_file: Path,
    required_services: tuple[str, ...],
    timeout_seconds: int,
    interval_seconds: float,
) -> bool:
    def _running_services() -> tuple[bool, str]:
        code, output = _run_command(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "ps",
                "--services",
                "--filter",
                "status=running",
            ],
            cwd=compose_file.parent.parent,
        )
        if code != 0:
            return False, output or "docker compose ps returned non-zero"
        running = {line.strip() for line in output.splitlines() if line.strip()}
        missing = [service for service in required_services if service not in running]
        if missing:
            return (
                False,
                f"missing running services: {', '.join(sorted(missing))}; "
                f"running={', '.join(sorted(running))}",
            )
        return True, f"services running: {', '.join(sorted(running))}"

    return _poll_until_ready(
        label="compose running services",
        checker=_running_services,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate deployment readiness before/after release rollouts."
    )
    parser.add_argument(
        "--backend-health-url",
        default="http://127.0.0.1:8100/healthz",
        help="Backend health URL (default: http://127.0.0.1:8100/healthz).",
    )
    parser.add_argument(
        "--bff-health-url",
        default="http://127.0.0.1:3001/healthz",
        help="BFF health URL (default: http://127.0.0.1:3001/healthz).",
    )
    parser.add_argument(
        "--web-url",
        default="http://127.0.0.1:3000/",
        help="Frontend URL (default: http://127.0.0.1:3000/).",
    )
    parser.add_argument(
        "--compose-file",
        default=str(Path("deploy") / "docker" / "docker-compose.yml"),
        help="Compose file used for service checks.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Maximum seconds to wait for each check (default: 180).",
    )
    parser.add_argument(
        "--retry-interval",
        type=float,
        default=2.0,
        help="Seconds between readiness polls (default: 2.0).",
    )
    parser.add_argument(
        "--skip-compose",
        action="store_true",
        help="Skip docker-compose service running checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    compose_file = Path(args.compose_file).expanduser().resolve()
    timeout = max(1, int(args.timeout_seconds))
    interval = max(0.25, float(args.retry_interval))

    checks: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
        (
            "backend healthz",
            lambda: _http_json(args.backend_health_url, timeout_seconds=min(10.0, interval * 3)),
        ),
        (
            "bff healthz",
            lambda: _http_json(args.bff_health_url, timeout_seconds=min(10.0, interval * 3)),
        ),
        (
            "spa-web root",
            lambda: _http_text(args.web_url, timeout_seconds=min(10.0, interval * 3)),
        ),
    ]

    compose_ok = True
    if not args.skip_compose:
        compose_ok = _check_compose_services(
            compose_file=compose_file,
            required_services=("backend-api", "backend-worker", "spa-bff", "spa-web"),
            timeout_seconds=timeout,
            interval_seconds=interval,
        )
        if not compose_ok:
            print("Deploy readiness check failed before endpoint probes.")
            return 1

    all_passed = True
    for label, checker in checks:
        ok = _poll_until_ready(
            label=label,
            checker=checker,
            timeout_seconds=timeout,
            interval_seconds=interval,
        )
        all_passed = all_passed and ok

    if compose_ok and all_passed:
        print("Deploy readiness gate passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
