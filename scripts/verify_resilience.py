#!/usr/bin/env python3
"""Run resilience verification checks for distributed cache and URL state recovery."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
import secrets
import tempfile
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/test_distributed_state_service.py",
    "tests/test_cache_utils.py",
    "tests/test_crud_backend_mutation_proxy.py",
    "tests/test_app_query_helpers.py",
    "tests/test_app_auth_helpers.py",
    "tests/test_atlas_workspace_scope_helpers.py",
    "tests/test_atlas_navigation_helpers.py",
    "tests/test_atlas_focus_selection_helpers.py",
    "tests/test_atlas_map_sidebar_helpers.py",
    "tests/test_atlas_map_chart_helpers.py",
)

_SMOKE_TEST_PATH = "tests/test_e2e_smoke.py"
_SMOKE_ENV_PREFIXES = (
    "AI_",
    "BFF_",
    "GEMINI_",
    "NEXT_PUBLIC_OKR_",
    "OKR_",
    "PDFSHIFT_",
    "SPA_",
    "SUPABASE_",
)
_SMOKE_ENV_NAMES = {
    "ALLOW_EXTERNAL_AI",
    "IMAGE",
    "NODE_ENV",
    "PDF_METHOD",
}


def _summarize_compose_failure(output: str) -> str:
    text = (output or "").lower()
    if "permission denied" in text and ("npipe" in text or ".docker" in text):
        return (
            "Docker daemon access was denied by environment policy.\n"
            "Observed: Docker Desktop config/engine access denied for current session. "
            "This commonly indicates restricted local permissions and is not a smoke-path logic bug."
        )
    if "unable to find image" in text or "pull access denied" in text:
        return (
            "Docker image availability/authenticity issue.\n"
            "Observed: required local images were not usable in this runtime. "
            "Verify docker compose builds/images are available and daemon credentials are valid."
        )
    if "no such file" in text or "not found" in text:
        return (
            "Missing compose artifact.\n"
            "Observed: compose file/service image references could not be resolved."
        )
    return "docker compose command returned a non-zero exit code."


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


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


def _free_local_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_smoke_env_file(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    service_token = secrets.token_hex(24)
    signing_secret = secrets.token_hex(32)
    session_secret = secrets.token_hex(32)
    bootstrap_password = f"Sm0ke!{secrets.token_urlsafe(24)}"
    postgres_password = secrets.token_hex(24)
    backend_host_port = _free_local_port()
    bff_host_port = _free_local_port()
    web_host_port = _free_local_port()
    postgres_host_port = _free_local_port()

    values = {
        "OKR_POSTGRES_USER": "okr",
        "OKR_POSTGRES_PASSWORD": postgres_password,
        "OKR_POSTGRES_DB": "okr",
        "OKR_POSTGRES_HOST_PORT": str(postgres_host_port),
        "OKR_DATABASE_URL": (
            "postgresql+psycopg2://"
            f"okr:{postgres_password}@postgres:5432/okr"
        ),
        "OKR_BACKEND_SERVICE_TOKEN": service_token,
        "OKR_BOOTSTRAP_ADMIN_PASSWORD": bootstrap_password,
        "OKR_BACKEND_ENFORCE_TOKEN": "true",
        "OKR_BACKEND_ENFORCE_REQUEST_SIGNING": "true",
        "OKR_BACKEND_HOST_PORT": str(backend_host_port),
        "OKR_BACKEND_BIND_ADDRESS": "127.0.0.1",
        "OKR_BACKEND_API_URL": "http://backend-api:8100",
        "OKR_BACKEND_SIGNING_SECRET": signing_secret,
        "NODE_ENV": "development",
        "BFF_SESSION_SECRET": session_secret,
        "BFF_SESSION_TTL_SECONDS": "3600",
        "BFF_COOKIE_SECURE": "false",
        "BFF_REQUEST_TIMEOUT_MS": "90000",
        "BFF_PUBLIC_ORIGIN": f"http://127.0.0.1:{bff_host_port}",
        "SPA_BFF_HOST_PORT": str(bff_host_port),
        "SPA_WEB_HOST_PORT": str(web_host_port),
        "SPA_BFF_BIND_ADDRESS": "127.0.0.1",
        "SPA_WEB_BIND_ADDRESS": "127.0.0.1",
        "OKR_BACKEND_HOST": "0.0.0.0",
        "BFF_HOST": "0.0.0.0",
        "OKR_STRICT_RUNTIME_PREFLIGHT": "false",
        "OKR_DATA_ACCESS_MODE": "database",
        "OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS": "120000",
        "OKR_BACKEND_PORT": "8100",
        "ALLOW_EXTERNAL_AI": "false",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "",
        "AI_BASE_URL": "",
        "AI_API_KEY": "",
        "PDFSHIFT_API_KEY": "",
    }

    # Keep values we need to call the services after startup.
    service_urls = {
        "backend_port": str(backend_host_port),
        "bff_port": str(bff_host_port),
        "web_port": str(web_host_port),
    }

    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return values, service_urls


def _build_smoke_pytest_env(
    smoke_env: dict[str, str], service_urls: dict[str, str]
) -> dict[str, str]:
    pytest_env = os.environ.copy()
    pytest_env.update(smoke_env)
    pytest_env.update(
        {
            "TOP10_SMOKE": "1",
            "TOP10_SMOKE_BFF_URL": f"http://127.0.0.1:{service_urls['bff_port']}",
            "TOP10_SMOKE_WEB_URL": f"http://127.0.0.1:{service_urls['web_port']}",
            "TOP10_SMOKE_USERNAME": "admin",
            "TOP10_SMOKE_PASSWORD": smoke_env["OKR_BOOTSTRAP_ADMIN_PASSWORD"],
        }
    )
    return pytest_env


def _run_compose(
    *,
    compose_file: Path,
    env_file: Path,
    compose_project: str,
    command: Iterable[str],
) -> tuple[int, str]:
    argv = ["docker", "compose", "-f", str(compose_file), "-p", compose_project]
    argv.append("--env-file")
    argv.append(str(env_file))
    argv.extend(command)

    # Docker Compose gives process variables precedence over --env-file. Remove
    # application-owned variables inherited from the runner, then overlay the
    # generated smoke values so CI secrets cannot redirect or reconfigure the
    # isolated stack.
    compose_env = {
        key: value
        for key, value in os.environ.items()
        if key not in _SMOKE_ENV_NAMES
        and not key.startswith(_SMOKE_ENV_PREFIXES)
    }
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        compose_env[key.strip()] = value

    return _run_command(argv, cwd=ROOT, env=compose_env)


def _redact_values(output: str, secret_values: Iterable[str]) -> str:
    redacted = str(output or "")
    for value in secret_values:
        secret_value = str(value or "")
        if secret_value:
            redacted = redacted.replace(secret_value, "[REDACTED]")
    return redacted


def _compose_failure_diagnostics(
    *,
    compose_file: Path,
    env_file: Path,
    compose_project: str,
    secret_values: Iterable[str],
) -> str:
    sections: list[str] = []
    for label, command in (
        ("docker compose ps", ["ps", "--all"]),
        (
            "docker compose logs",
            [
                "logs",
                "--no-color",
                "--tail",
                "120",
                "postgres",
                "backend-api",
                "backend-worker",
                "spa-bff",
                "spa-web",
            ],
        ),
    ):
        code, output = _run_compose(
            compose_file=compose_file,
            env_file=env_file,
            compose_project=compose_project,
            command=command,
        )
        sections.append(
            f"{label} (exit={code}):\n"
            f"{_redact_values(output or '<no output>', secret_values)}"
        )
    return "\n\n".join(sections)


def _smoke_check_services(
    base_bff_url: str,
    base_backend_url: str,
    base_web_url: str,
    timeout_seconds: int,
) -> CheckResult:
    deadline = time.time() + float(timeout_seconds)
    last_errors: dict[str, str] = {}
    while time.time() < deadline:
        service_checks = {
            "backend-api": f"{base_backend_url}/healthz",
            "spa-bff": f"{base_bff_url}/healthz",
            "spa-web": base_web_url,
        }
        ready_services: set[str] = set()
        for service_name, url in service_checks.items():
            try:
                import urllib.request

                with urllib.request.urlopen(url, timeout=2) as response:
                    status = int(getattr(response, "status", 0) or 0)
                if 200 <= status < 300:
                    ready_services.add(service_name)
                    last_errors.pop(service_name, None)
                else:
                    last_errors[service_name] = f"HTTP {status}"
            except Exception as exc:
                last_errors[service_name] = f"{type(exc).__name__}: {exc}"
        if len(ready_services) == len(service_checks):
                return CheckResult(
                    name="compose_service_readiness",
                    status="pass",
                    detail=(
                        "Backend, spa-bff, and spa-web became ready for smoke execution."
                    ),
                )
        time.sleep(1.5)
    error_summary = "; ".join(
        f"{service}={error}" for service, error in sorted(last_errors.items())
    )
    return CheckResult(
        name="compose_service_readiness",
        status="fail",
        detail=(
            "Services did not become healthy within smoke startup timeout."
            + (f" Last observations: {error_summary}" if error_summary else "")
        ),
    )


def _run_smoke_compose(
    *,
    args: argparse.Namespace,
) -> CheckResult:
    if not args.compose_file.exists():
        return CheckResult(
            name="compose_smoke",
            status="skip",
            detail=f"Compose file not found: {args.compose_file}",
        )

    compose_project = str(args.compose_project).strip() or f"okr-smoke-{secrets.token_hex(3)}"
    compose_file = args.compose_file

    with tempfile.TemporaryDirectory(prefix="okr-smoke-") as workdir:
        env_path = Path(workdir) / "smoke.env"
        smoke_env, service_urls = _write_smoke_env_file(env_path)
        pytest_env = _build_smoke_pytest_env(smoke_env, service_urls)
        secret_values = (
            smoke_env["OKR_BACKEND_SERVICE_TOKEN"],
            smoke_env["OKR_BACKEND_SIGNING_SECRET"],
            smoke_env["BFF_SESSION_SECRET"],
            smoke_env["OKR_BOOTSTRAP_ADMIN_PASSWORD"],
            smoke_env["OKR_POSTGRES_PASSWORD"],
        )

        try:
            compose_up = _run_compose(
                compose_file=compose_file,
                env_file=env_path,
                compose_project=compose_project,
                command=[
                    "up",
                    "-d",
                    "--build",
                    "backend-api",
                    "backend-worker",
                    "spa-bff",
                    "spa-web",
                ],
            )
            if compose_up[0] != 0:
                summary = _summarize_compose_failure(compose_up[1])
                diagnostics = _compose_failure_diagnostics(
                    compose_file=compose_file,
                    env_file=env_path,
                    compose_project=compose_project,
                    secret_values=secret_values,
                )
                compose_output = _redact_values(compose_up[1], secret_values)
                return CheckResult(
                    name="compose_smoke",
                    status="fail",
                    detail=(
                        "docker compose up failed for smoke run.\n"
                        f"{summary}\n"
                        f"command_exit={compose_up[0]}\n{compose_output}"
                        f"\n\n{diagnostics}"
                    ),
                )

            readiness = _smoke_check_services(
                base_bff_url=pytest_env["TOP10_SMOKE_BFF_URL"],
                base_backend_url=f"http://127.0.0.1:{service_urls['backend_port']}",
                base_web_url=pytest_env["TOP10_SMOKE_WEB_URL"],
                timeout_seconds=180,
            )
            if readiness.status != "pass":
                diagnostics = _compose_failure_diagnostics(
                    compose_file=compose_file,
                    env_file=env_path,
                    compose_project=compose_project,
                    secret_values=secret_values,
                )
                return CheckResult(
                    name=readiness.name,
                    status=readiness.status,
                    detail=f"{readiness.detail}\n\n{diagnostics}",
                )

            pytest_cmd = [sys.executable, "-m", "pytest", "-q", _SMOKE_TEST_PATH]
            pycode, pyout = _run_command(
                pytest_cmd,
                cwd=ROOT,
                env=pytest_env,
            )
            if pycode != 0:
                return CheckResult(
                    name="compose_smoke_pytest",
                    status="fail",
                    detail=pyout or "Smoke pytest command failed.",
                )
            return CheckResult(
                name="compose_smoke_pytest",
                status="pass",
                detail="Full-stack compose smoke test passed.",
            )
        finally:
            down_result = _run_compose(
                compose_file=compose_file,
                env_file=env_path,
                compose_project=compose_project,
                command=["down", "--volumes", "--remove-orphans"],
            )
            if down_result[0] != 0:
                print(f"[WARN] docker compose down returned {down_result[0]}.")
                print(down_result[1])


def _run_pytest(*, targets: Iterable[str], extra_args: Iterable[str]) -> CheckResult:
    test_targets = [str(target).strip() for target in targets if str(target).strip()]
    existing_targets = [path for path in test_targets if Path(path).exists()]
    missing_targets = [path for path in test_targets if not Path(path).exists()]

    if missing_targets:
        print(f"[INFO] Skipping missing pytest targets: {', '.join(missing_targets)}")

    if not existing_targets:
        return CheckResult(
            name="pytest_resilience_suite",
            status="skip",
            detail="No valid pytest targets found.",
        )

    if not test_targets:
        return CheckResult(
            name="pytest_resilience_suite",
            status="skip",
            detail="No pytest targets specified.",
        )

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *existing_targets,
        *[str(arg) for arg in extra_args if str(arg).strip()],
    ]
    print(f"Running: {' '.join(cmd)}")
    return_code, output = _run_command(cmd, cwd=ROOT)
    if return_code != 0:
        detail = (
            output or "Pytest exited with a non-zero status and no output was captured."
        )
        return CheckResult(
            name="pytest_resilience_suite",
            status="fail",
            detail=detail,
        )

    return CheckResult(
        name="pytest_resilience_suite",
        status="pass",
        detail=output or "Pytest suite passed.",
    )


def _bootstrap_import_path() -> None:
    root_src = str(ROOT.resolve())
    if root_src not in sys.path:
        sys.path.insert(0, root_src)


def _run_live_backend_checks(
    *,
    actor_username: str,
    probe_key_prefix: str,
    require_live_backend: bool,
) -> list[CheckResult]:
    _bootstrap_import_path()
    from src.config_runtime import get_config_value
    from src.services import distributed_state_service

    backend_url = str(get_config_value("OKR_BACKEND_API_URL", "")).strip()
    if not backend_url:
        status = "fail" if require_live_backend else "skip"
        return [
            CheckResult(
                name="live_distributed_state_roundtrip",
                status=status,
                detail=(
                    "OKR_BACKEND_API_URL is empty. "
                    "Set backend URL and service credentials to run live checks."
                ),
            )
        ]

    now_ns = int(time.time_ns())
    probe_key = f"{str(probe_key_prefix).strip()}:{now_ns}:roundtrip"
    probe_value = str(now_ns)

    results: list[CheckResult] = []

    set_ok = distributed_state_service.set_distributed_state(
        probe_key,
        probe_value,
        actor_username=actor_username,
    )
    if not set_ok:
        results.append(
            CheckResult(
                name="live_distributed_state_roundtrip",
                status="fail",
                detail=(
                    "Failed to set distributed state probe key. "
                    "Check backend URL/token/signing config and backend health."
                ),
            )
        )
        return results

    roundtrip_value = distributed_state_service.get_distributed_state(
        probe_key,
        actor_username=actor_username,
    )
    if roundtrip_value != probe_value:
        results.append(
            CheckResult(
                name="live_distributed_state_roundtrip",
                status="fail",
                detail=(
                    f"Roundtrip mismatch for '{probe_key}': "
                    f"expected '{probe_value}', got '{roundtrip_value}'."
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="live_distributed_state_roundtrip",
                status="pass",
                detail=f"Probe key '{probe_key}' set/read roundtrip succeeded.",
            )
        )

    before_ts = distributed_state_service.get_last_invalidation_timestamp()
    broadcast_ok = distributed_state_service.broadcast_cache_invalidation(
        actor_username=actor_username
    )
    after_ts = distributed_state_service.get_last_invalidation_timestamp()

    if not broadcast_ok:
        results.append(
            CheckResult(
                name="live_cache_invalidation_signal",
                status="fail",
                detail="Failed to broadcast cache invalidation signal.",
            )
        )
    elif int(after_ts) <= int(before_ts):
        results.append(
            CheckResult(
                name="live_cache_invalidation_signal",
                status="fail",
                detail=(
                    "Invalidation timestamp did not advance. "
                    f"before={before_ts}, after={after_ts}."
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="live_cache_invalidation_signal",
                status="pass",
                detail=f"Invalidation timestamp advanced: {before_ts} -> {after_ts}.",
            )
        )

    return results


def _print_results(results: list[CheckResult]) -> None:
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.detail}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run resilience verification checks for distributed cache invalidation "
            "and URL-state failover support."
        )
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip the default resilience pytest subset.",
    )
    parser.add_argument(
        "--compose-smoke",
        action="store_true",
        help="Start docker compose services and run the full-stack smoke test.",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "deploy"
        / "docker"
        / "docker-compose.yml",
        help="Compose file for smoke execution.",
    )
    parser.add_argument(
        "--compose-project",
        default="okr-productionization-smoke",
        help="Docker compose project name for smoke execution.",
    )
    parser.add_argument(
        "--pytest-target",
        action="append",
        default=[],
        help=(
            "Additional pytest target to include. "
            "If any are provided, they are appended to the default subset."
        ),
    )
    parser.add_argument(
        "--extra-pytest-arg",
        action="append",
        default=[],
        help="Extra argument forwarded to pytest (can be specified multiple times).",
    )
    parser.add_argument(
        "--live-backend-check",
        action="store_true",
        help="Run live backend distributed-state checks through backend API endpoints.",
    )
    parser.add_argument(
        "--require-live-backend",
        action="store_true",
        help="Fail if live backend checks cannot run or do not pass.",
    )
    parser.add_argument(
        "--actor",
        default="system",
        help="Actor username used for live backend checks (default: system).",
    )
    parser.add_argument(
        "--probe-key-prefix",
        default="okr:resilience:probe",
        help="Distributed-state probe key prefix for live checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    run_live = bool(args.live_backend_check or args.require_live_backend)

    results: list[CheckResult] = []

    if not args.skip_pytest:
        combined_targets = list(DEFAULT_PYTEST_TARGETS)
        combined_targets.extend(args.pytest_target)
        results.append(
            _run_pytest(
                targets=combined_targets,
                extra_args=args.extra_pytest_arg,
            )
        )

    if run_live:
        results.extend(
            _run_live_backend_checks(
                actor_username=str(args.actor).strip() or "system",
                probe_key_prefix=str(args.probe_key_prefix).strip()
                or "okr:resilience:probe",
                require_live_backend=bool(args.require_live_backend),
            )
        )
    if args.compose_smoke:
        results.append(_run_smoke_compose(args=args))

    if not results:
        print("No checks were selected.")
        return 1

    _print_results(results)

    failed = [item for item in results if item.status == "fail"]
    if failed:
        print(f"Resilience verification failed ({len(failed)} check(s)).")
        return 1

    print("Resilience verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
