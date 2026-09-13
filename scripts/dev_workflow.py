#!/usr/bin/env python3
"""Orchestrate the isolated disposable Docker development environment."""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "deploy" / "docker" / "docker-compose.yml"
PROJECT = "okr-dev"


def _available_host_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", preferred))
        except OSError:
            probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _runtime_environment() -> tuple[dict[str, str], str]:
    environment = os.environ.copy()
    password = str(environment.get("OKR_DEV_ADMIN_PASSWORD", "")).strip() or f"Aa1!{secrets.token_urlsafe(18)}"
    environment.update(
        {
            "OKR_DEV_DISPOSABLE": "1",
            "OKR_ENV": "development",
            "OKR_SAAS_MODE": "false",
            "OKR_DEPLOYMENT_PROFILE": "on_premise",
            "OKR_DATA_ACCESS_MODE": "database",
            "OKR_ALLOW_NON_SUPABASE_DB": "true",
            "OKR_DATABASE_URL": "postgresql+psycopg2://okr:okr_dev_password@postgres:5432/okr",
            "OKR_POSTGRES_USER": "okr",
            "OKR_POSTGRES_PASSWORD": "okr_dev_password",
            "OKR_POSTGRES_DB": "okr",
            "OKR_POSTGRES_HOST_PORT": str(_available_host_port(15432)),
            "OKR_BACKEND_HOST_PORT": str(_available_host_port(8100)),
            "SPA_BFF_HOST_PORT": str(_available_host_port(3001)),
            "SPA_WEB_HOST_PORT": str(_available_host_port(3000)),
            "OKR_DEV_ADMIN_PASSWORD": password,
            "OKR_BOOTSTRAP_ADMIN_PASSWORD": password,
            "OKR_BACKEND_SERVICE_TOKEN": secrets.token_hex(32),
            "OKR_BACKEND_SIGNING_SECRET": secrets.token_hex(32),
            "BFF_SESSION_SECRET": secrets.token_hex(32),
        }
    )
    return environment, password


def _compose(*args: str, environment: dict[str, str]) -> None:
    command = ["docker", "compose", "-p", PROJECT, "-f", str(COMPOSE_FILE), *args]
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def _published_port(service: str, container_port: int, environment: dict[str, str]) -> str:
    command = [
        "docker", "compose", "-p", PROJECT, "-f", str(COMPOSE_FILE),
        "port", service, str(container_port),
    ]
    result = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True, check=False,
    )
    published = result.stdout.strip().rsplit(":", 1)
    return published[-1] if result.returncode == 0 and len(published) == 2 else ""


def _print_urls(environment: dict[str, str], password: str | None = None, *, actual: bool = False) -> None:
    web_port = _published_port("spa-web", 3000, environment) if actual else ""
    bff_port = _published_port("spa-bff", 3001, environment) if actual else ""
    api_port = _published_port("backend-api", 8100, environment) if actual else ""
    web_port = web_port or environment["SPA_WEB_HOST_PORT"]
    bff_port = bff_port or environment["SPA_BFF_HOST_PORT"]
    api_port = api_port or environment["OKR_BACKEND_HOST_PORT"]
    print(f"[DEV] Web: http://127.0.0.1:{web_port}")
    print(f"[DEV] BFF health: http://127.0.0.1:{bff_port}/healthz")
    print(f"[DEV] API health: http://127.0.0.1:{api_port}/healthz")
    print("[DEV] Login username: admin")
    if password:
        print(f"[DEV] Temporary password: {password}")


def reset() -> int:
    environment, password = _runtime_environment()
    _compose("down", "--volumes", environment=environment)
    _compose("up", "-d", "--build", "--wait", "--wait-timeout", "120", "postgres", environment=environment)
    _compose(
        "run", "--build", "--rm", "--no-deps", "backend-api",
        "alembic", "upgrade", "head", environment=environment,
    )
    _compose(
        "run", "--rm", "--no-deps", "backend-api", "python", "scripts/seed_dev_demo.py",
        "--confirm-disposable", "--reset-admin-password", environment=environment,
    )
    _compose(
        "up", "-d", "--build", "--wait", "--wait-timeout", "120",
        "backend-api", "backend-worker", "spa-bff", "spa-web", environment=environment,
    )
    _print_urls(environment, password)
    return 0


def seed() -> int:
    environment, _password = _runtime_environment()
    _compose(
        "run", "--rm", "--no-deps", "backend-api", "python", "scripts/seed_dev_demo.py",
        "--confirm-disposable", environment=environment,
    )
    return 0


def status() -> int:
    environment, _password = _runtime_environment()
    _compose("ps", environment=environment)
    _print_urls(environment, actual=True)
    return 0


def clean() -> int:
    environment, _password = _runtime_environment()
    _compose("down", "--volumes", environment=environment)
    print(f"[DEV] Removed disposable Compose project {PROJECT} and its volumes.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("reset", "seed", "status", "clean"))
    args = parser.parse_args(argv)
    try:
        return {"reset": reset, "seed": seed, "status": status, "clean": clean}[args.command]()
    except FileNotFoundError:
        print("[DEV] Docker Compose is required. Install Docker Desktop and retry.", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(
            f"[DEV] Docker Compose could not complete the {args.command} operation "
            f"(exit={exc.returncode}). Check Docker Desktop/daemon permissions and retry.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
