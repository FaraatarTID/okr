"""Verify the repository's Twelve-Factor process and disposability contract.

This is a provider-independent, secret-safe static check. It validates the
Compose topology without starting containers or contacting an external
platform.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SERVICE_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.MULTILINE)


def _read_compose(root: Path) -> str:
    try:
        return (root / "deploy/docker/docker-compose.yml").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return ""


def _check_runtime_templates(root: Path) -> str | None:
    for relative in (
        "deploy/docker/.env.example",
        "deploy/docker/.env.saas.example",
        "deploy/darkube/prerelease/.env.example",
    ):
        try:
            content = (root / relative).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            continue
        if re.search(r"^\s*OKR_CONTROL_PLANE_STATE_PATH\s*=", content, re.MULTILINE):
            return f"normal runtime template enables process-local state: {relative}"
    return None


def _service_block(compose: str, service: str) -> str:
    match = re.search(rf"^  {re.escape(service)}:\s*$", compose, re.MULTILINE)
    if not match:
        return ""
    remainder = compose[match.end() :]
    next_service = re.search(r"^  [A-Za-z0-9_-]+:\s*$", remainder, re.MULTILINE)
    return remainder[: next_service.start()] if next_service else remainder


def _check_ports(compose: str) -> str | None:
    required = {
        "backend-api": ("OKR_BACKEND_PORT", "OKR_BACKEND_HOST_PORT", "OKR_BACKEND_PORT"),
        "spa-bff": ("BFF_PORT", "SPA_BFF_HOST_PORT", "BFF_PORT"),
        "spa-web": ("PORT", "SPA_WEB_HOST_PORT", "SPA_WEB_PORT"),
    }
    for service, variables in required.items():
        block = _service_block(compose, service)
        if (
            not block
            or "ports:" not in block
            or not all(var in block for var in variables[:2])
            or not re.search(rf"\b{re.escape(variables[0])}=\$\{{", block)
            or not re.search(rf"\$\{{{re.escape(variables[2])}(?::[-?][^}}]*)?}}", block)
        ):
            return f"environment-driven ports are incomplete for {service}"
    return None


def _check_health(compose: str) -> str | None:
    for service in ("backend-api", "spa-bff"):
        block = _service_block(compose, service)
        if "healthcheck:" not in block or "/healthz" not in block:
            return f"health/readiness endpoint is incomplete for {service}"
    return None


def _check_restart(compose: str) -> str | None:
    for service in ("backend-api", "backend-worker", "spa-bff", "spa-web"):
        if "restart: unless-stopped" not in _service_block(compose, service):
            return f"restart/disposability policy is incomplete for {service}"
    return None


def _check_processes(compose: str) -> str | None:
    api = _service_block(compose, "backend-api")
    worker = _service_block(compose, "backend-worker")
    if "python -m backend_app.run_api" not in api or "python -m backend_app.worker" not in worker:
        return "separate API and worker processes are not declared"
    return None


def _check_volumes(compose: str) -> str | None:
    api = _service_block(compose, "backend-api")
    worker = _service_block(compose, "backend-worker")
    postgres = _service_block(compose, "postgres")
    if "volumes:" not in compose or "okr-postgres-data:" not in compose:
        return "database state volume is not explicitly declared"
    if "/var/lib/postgresql/data" not in postgres:
        return "database state volume is not mounted on postgres"
    if "okr-control-plane-state:" in compose or "/var/lib/okr" in api or "/var/lib/okr" in worker:
        return "control-plane state must not require a process-local volume"
    return None


def verify_repository(root: Path = ROOT) -> list[str]:
    compose = _read_compose(root)
    if not compose:
        return ["process contract: deploy/docker/docker-compose.yml is missing"]
    checks = (_check_ports, _check_health, _check_restart, _check_processes, _check_volumes)
    failures = [f"process contract: {failure}" for check in checks if (failure := check(compose))]
    if template_failure := _check_runtime_templates(root):
        failures.append(f"process contract: {template_failure}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    failures = verify_repository(args.root.resolve())
    if failures:
        print("[PROCESS-CONTRACT] Contract failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("[PROCESS-CONTRACT] Process/disposability contract passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
