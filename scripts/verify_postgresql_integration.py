#!/usr/bin/env python3
"""Run PostgreSQL-backed integrity checks using a real database runtime."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TESTS = ("tests/test_postgres_integration_smoke.py",)

_POSTGRES_DEFAULT_URL = (
    "postgresql+psycopg2://okr:okr_dev_password@127.0.0.1:15432/okr"
)


def _run_command(
    argv: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> tuple[int, str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    output = "\n".join(
        [chunk for chunk in [completed.stdout, completed.stderr] if chunk]
    ).strip()
    return int(completed.returncode), output


def _run_compose(
    *,
    compose_file: Path,
    compose_project: str,
    command: list[str],
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    argv = ["docker", "compose", "-f", str(compose_file), "-p", compose_project]
    argv.extend(command)
    return _run_command(argv, cwd=ROOT, env=env)


def _wait_for_tcp(host: str, port: int, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=2):
                return True
        except OSError:
            time.sleep(1.0)
    return False


def _require_postgres_available(database_url: str) -> None:
    lowered = str(database_url).strip().lower()
    if not lowered.startswith("postgresql+psycopg2://"):
        raise RuntimeError(
            "PostgreSQL verification requires a Postgres DSN in "
            "OKR_DATABASE_URL, DATABASE_URL, or --database-url."
        )


def _run_postgres_smoke(*, args: argparse.Namespace) -> int:
    database_url = (
        args.database_url
        or os.getenv("OKR_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or _POSTGRES_DEFAULT_URL
    ).strip()
    _require_postgres_available(database_url)

    compose_file = Path(args.compose_file)
    if not compose_file.exists():
        raise RuntimeError(f"Compose file not found: {compose_file}")

    project = str(args.compose_project).strip() or "okr-postgres-integration"
    started_postgres = False

    if args.ensure_docker_service:
        env = os.environ.copy()
        env["OKR_POSTGRES_HOST_PORT"] = str(args.postgres_host_port)
        env["OKR_POSTGRES_USER"] = args.postgres_user
        env["OKR_POSTGRES_PASSWORD"] = args.postgres_password
        env["OKR_POSTGRES_DB"] = args.postgres_db

        up_code, up_out = _run_compose(
            compose_file=compose_file,
            compose_project=project,
            command=["up", "-d", "postgres"],
            env=env,
        )
        if up_code != 0:
            raise RuntimeError(
                "docker compose up postgres failed for PostgreSQL integration verification.\n"
                f"command_exit={up_code}\n{up_out}"
            )
        started_postgres = True

    try:
        if not _wait_for_tcp("127.0.0.1", args.postgres_host_port, timeout_seconds=80):
            raise RuntimeError(
                "PostgreSQL service did not become reachable on configured host port."
            )

        test_env = os.environ.copy()
        test_env["OKR_DATABASE_URL"] = database_url
        test_env["DATABASE_URL"] = database_url
        test_env["OKR_ALLOW_NON_SUPABASE_DB"] = "true"
        test_env["OKR_ENV"] = "development"

        pytest_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *args.extra_pytest_arg,
            *args.test_targets,
        ]
        return_code, out = _run_command(pytest_cmd, cwd=ROOT, env=test_env)
        print(out or "")
        return int(return_code)
    finally:
        if started_postgres:
            down_code, down_out = _run_compose(
                compose_file=compose_file,
                compose_project=project,
                command=["down", "--volumes", "--remove-orphans"],
            )
            if down_code != 0:
                print(f"[WARN] docker compose down returned {down_code}.")
                print(down_out)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run lightweight PostgreSQL-backed productionization checks."
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL URL used for integration checks (must be postgresql+psycopg2://).",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=ROOT / "deploy" / "docker" / "docker-compose.yml",
        help="Compose file used when ensure-docker-service is enabled.",
    )
    parser.add_argument(
        "--compose-project",
        default="okr-postgres-integration",
        help="Compose project name for temporary postgres service.",
    )
    parser.add_argument("--postgres-host-port", type=int, default=15432)
    parser.add_argument("--postgres-user", default="okr")
    parser.add_argument("--postgres-password", default="okr_dev_password")
    parser.add_argument("--postgres-db", default="okr")
    parser.add_argument(
        "--ensure-docker-service",
        action="store_true",
        help=(
            "Start and stop postgres via docker-compose if set. "
            "Otherwise assume an external service is already available."
        ),
    )
    parser.add_argument(
        "--extra-pytest-arg",
        action="append",
        default=[],
        help="Extra argument for pytest (can be repeated).",
    )
    parser.add_argument(
        "--test-target",
        action="append",
        default=list(DEFAULT_TESTS),
        dest="test_targets",
        help="Additional test targets to run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    return _run_postgres_smoke(args=args)


if __name__ == "__main__":
    raise SystemExit(main())
