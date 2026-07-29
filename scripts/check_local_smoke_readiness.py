#!/usr/bin/env python3
"""Deterministic preflight checks before local hybrid bootstrap and smoke-equivalent runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import os
import shutil
import socket
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""


def _check_binary(name: str) -> CheckResult:
    if shutil.which(name):
        return CheckResult(name=f"{name} available", passed=True)
    return CheckResult(
        name=f"{name} available",
        passed=False,
        details="Install/enable this tool and retry.",
    )


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        values[key.strip()] = val.strip().strip('"\'')
    return values


def _env_value(name: str, env_file: dict[str, str]) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    return env_file.get(name, "").strip()


def _check_db_env(root: Path, env_file: dict[str, str], docker_env_name: str) -> CheckResult:
    data_access_mode = _env_value("OKR_DATA_ACCESS_MODE", env_file) or "database"
    if data_access_mode.lower() == "supabase_api":
        missing = []
        for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
            if not _env_value(name, env_file):
                missing.append(name)
        if missing:
            return CheckResult(
                name="Data access mode variables",
                passed=False,
                details=(
                    f"{docker_env_name} indicates supabase_api but missing: {', '.join(missing)}. "
                    "Set in environment or deploy/docker/.env"
                ),
            )
        return CheckResult(
            name="Data access mode variables",
            passed=True,
            details="supabase_api credentials are present",
        )

    if not _env_value("OKR_DATABASE_URL", env_file):
        return CheckResult(
            name="Data access mode variables",
            passed=False,
            details=(
                "Missing OKR_DATABASE_URL for database mode. "
                "Set in environment or deploy/docker/.env"
            ),
        )
    return CheckResult(name="Data access mode variables", passed=True)


def _check_required_env(names: list[str], env_file: dict[str, str]) -> CheckResult:
    missing = [name for name in names if not _env_value(name, env_file)]
    if missing:
        return CheckResult(
            name="Required secrets/keys",
            passed=False,
            details=f"Missing: {', '.join(missing)}",
        )
    return CheckResult(name="Required secrets/keys", passed=True)


def _check_ports(name: str, ports: list[int]) -> CheckResult:
    busy = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(str(port))

    if busy:
        return CheckResult(
            name=f"Port conflict check: {name}",
            passed=False,
            details=(
                f"Ports already in use locally: {', '.join(busy)}. "
                "Stop conflicting services before launching local hybrid stack."
            ),
        )
    return CheckResult(name=f"Port conflict check: {name}", passed=True)


def _check_docker_daemon() -> CheckResult:
    if shutil.which("docker") is None:
        return CheckResult(
            name="Docker executable",
            passed=False,
            details="docker command not found in PATH.",
        )
    try:
        completed = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        return CheckResult(
            name="Docker daemon",
            passed=False,
            details=f"Failed to run docker info: {exc}",
        )
    if completed.returncode != 0:
        return CheckResult(
            name="Docker daemon",
            passed=False,
            details=(
                "docker is installed but daemon is not available."
            ),
        )
    return CheckResult(name="Docker daemon", passed=True)


def verify(root: Path, require_docker: bool = False) -> int:
    env_file = root / "deploy" / "docker" / ".env"
    env_values = _parse_env_file(env_file)

    if (
        os.getenv("CHECK_LOCAL_SMOKE_REQUIRE_DOCKER", "").strip().lower()
        in {"1", "true", "yes", "on"}
    ):
        require_docker = True

    checks: list[CheckResult] = [
        _check_binary("python"),
        _check_binary("node"),
        _check_binary("npm"),
        _check_binary("powershell"),
        _check_binary("npx"),
    ]
    checks.append(_check_db_env(root, env_values, str(env_file)))

    required = [
        "BFF_SESSION_SECRET",
        "OKR_BACKEND_SERVICE_TOKEN",
        "OKR_DATA_ACCESS_MODE",
    ]
    checks.append(_check_required_env(required, env_values))
    checks.append(_check_ports("hybrid services", [8100, 3001, 3000]))

    if require_docker:
        checks.append(_check_docker_daemon())
    else:
        checks.append(
            CheckResult(
                name="Docker daemon (optional)",
                passed=True,
                details=(
                    "Skipped strict daemon check; set CHECK_LOCAL_SMOKE_REQUIRE_DOCKER=1 "
                    "to enforce docker daemon verification."
                ),
            )
        )

    failed = [check for check in checks if not check.passed]
    for check in checks:
        status = "[PASS]" if check.passed else "[FAIL]"
        line = f"{status} {check.name}"
        if check.details:
            line += f" :: {check.details}"
        print(line)

    if failed:
        print("")
        print("Preflight guidance:")
        print("- Configure required env vars in deploy\\docker\\.env or current shell")
        print("- Ensure Node/npm binaries are on PATH")
        print("- Stop any conflicting local processes before starting ports 8100/3001/3000")
        print("- If running compose-based verification, ensure docker daemon is running")
        return 1

    print("Local smoke readiness preflight passed.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic preflight checks for local hybrid startup readiness."
    )
    parser.add_argument(
        "--root",
        default=str(PROJECT_ROOT),
        help="Repository root.",
    )
    parser.add_argument(
        "--require-docker-daemon",
        action="store_true",
        help=(
            "Require docker daemon availability in preflight checks. "
            "Equivalent to CHECK_LOCAL_SMOKE_REQUIRE_DOCKER=1."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return verify(Path(args.root).resolve(), require_docker=bool(args.require_docker_daemon))


if __name__ == "__main__":
    raise SystemExit(main())
