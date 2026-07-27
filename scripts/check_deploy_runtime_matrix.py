#!/usr/bin/env python3
"""Run deployment runtime validation across multiple realistic environment scenarios."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import shutil


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimeScenario:
    name: str
    db_url: str = "postgresql+psycopg2://okr:okr_ci_pass_2026@postgres:5432/okr?sslmode=require"
    backend_api_url: str = "http://backend-api:8100"
    pdf_method: str = "chromium"
    pdfshift_api_key: str = ""
    backend_security_state_backend: str = "database"
    backend_security_state_redis_url: str = ""
    backend_bind_address: str = "127.0.0.1"


SCENARIOS = (
    RuntimeScenario(name="database_chromium"),
    RuntimeScenario(
        name="database_pdfshift",
        pdf_method="pdfshift",
        pdfshift_api_key="runtime_smoke_pdfshift_key_please_replace",
    ),
    RuntimeScenario(
        name="redis_backend",
        backend_security_state_backend="redis",
        backend_security_state_redis_url="redis://redis.internal:6379/0",
    ),
)


def _build_env_lines(scenario: RuntimeScenario) -> list[str]:
    return [
        "PORT=8501",
        "HOST_PORT=8501",
        "BASE_URL_PATH=",
        f"OKR_DATABASE_URL={scenario.db_url}",
        f"OKR_BACKEND_API_URL={scenario.backend_api_url}",
        "OKR_BACKEND_SERVICE_TOKEN=runtime-smoke-token-please-change-2026-ci",
        "OKR_BACKEND_SIGNING_SECRET=runtime-smoke-signing-secret-please-change-2026",
        "BFF_SESSION_SECRET=runtime-smoke-bff-session-secret-very-long",
        "OKR_BOOTSTRAP_ADMIN_PASSWORD=RuntimeAdminPassword!2026",
        "OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true",
        "OKR_BACKEND_PROXY_MUTATIONS=true",
        "OKR_BACKEND_PROXY_READS=true",
        f"OKR_BACKEND_SECURITY_STATE_BACKEND={scenario.backend_security_state_backend}",
        f"OKR_BACKEND_SECURITY_STATE_REDIS_URL={scenario.backend_security_state_redis_url}",
        f"OKR_BACKEND_BIND_ADDRESS={scenario.backend_bind_address}",
        "OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false",
        "OKR_ALLOW_LOCAL_READ_FALLBACK=false",
        "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false",
        "OKR_ENFORCE_STRONG_PASSWORD_POLICY=true",
        f"PDF_METHOD={scenario.pdf_method}",
        f"PDFSHIFT_API_KEY={scenario.pdfshift_api_key}",
        "OKR_STRICT_RUNTIME_PREFLIGHT=true",
        "BFF_COOKIE_SECURE=true",
    ]


def _run_checked(cmd: list[str], *, env_file: Path, context: str) -> None:
    result = subprocess.run(cmd, check=False, cwd=ROOT, text=True, capture_output=True)
    stdout = result.stdout
    stderr = result.stderr

    if result.returncode != 0:
        raise RuntimeError(
            f"{context} failed for {env_file.name}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run runtime deploy config validation across scenarios."
    )
    parser.add_argument(
        "--require-docker",
        action="store_true",
        help="Fail if Docker is unavailable instead of skipping compose checks.",
    )
    return parser.parse_args(argv)


def run_matrix(*, require_docker: bool) -> None:
    docker_available = bool(shutil.which("docker"))
    if not docker_available and require_docker:
        raise RuntimeError(
            "Docker is required but unavailable. Install Docker Desktop/Engine to run "
            "runtime matrix validation in strict mode."
        )
    if not docker_available:
        print(
            "⚠️ Docker is not available in this environment. Compose checks are skipped; "
            "runtime config checks will still run.",
            file=sys.stderr,
        )

    with TemporaryDirectory(prefix="okr-runtime-matrix-") as tmpdir:
        base = Path(tmpdir)
        for scenario in SCENARIOS:
            env_file = base / f"{scenario.name}.env"
            env_file.write_text(
                "\n".join(_build_env_lines(scenario)) + "\n",
                encoding="utf-8",
            )

            _run_checked(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "check_deploy_config.py"),
                    "--mode",
                    "runtime",
                    "--env-file",
                    str(env_file),
                ],
                env_file=env_file,
                context="Runtime deploy config validation",
            )

            if docker_available:
                compose_output = base / f"{scenario.name}-compose.yaml"
                result = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        str(ROOT / "deploy" / "docker" / "docker-compose.yml"),
                        "--env-file",
                        str(env_file),
                        "config",
                    ],
                    check=False,
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Docker compose config failed for {scenario.name}.\n"
                        f"stdout:\n{result.stdout}\n"
                        f"stderr:\n{result.stderr}"
                    )
                compose_output.write_text(result.stdout, encoding="utf-8")

                rendered = result.stdout
                if (
                    "OKR_BACKEND_SERVICE_TOKEN=runtime-smoke-token-please-change-2026-ci"
                    not in rendered
                ):
                    raise RuntimeError(
                        "Compose expansion did not preserve OKR_BACKEND_SERVICE_TOKEN for "
                        f"{scenario.name}."
                    )
                if (
                    "BFF_SESSION_SECRET=runtime-smoke-bff-session-secret-very-long"
                    not in rendered
                ):
                    raise RuntimeError(
                        "Compose expansion did not preserve BFF_SESSION_SECRET for "
                        f"{scenario.name}."
                    )

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    run_matrix(require_docker=args.require_docker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
