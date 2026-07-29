#!/usr/bin/env python3
"""Run deployment runtime validation across multiple realistic environment scenarios."""

from __future__ import annotations

import os
import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_SERVICE_PORT_RE = re.compile(
    r"^([0-9]{1,5}:[0-9]{1,5}:[0-9]{1,5}|[0-9]{1,5}:[0-9]{1,5}|[0-9]{1,5})$"
)


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


def _load_env_file_values(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            values[key] = value
    return values


def _run_compose_config(env_file: Path, compose_file: Path) -> str:
    env_file_values = _load_env_file_values(env_file)

    attempts: tuple[tuple[list[str], dict[str, str] | None], ...] = (
        (["--env-file", str(env_file), "--format", "json"], None),
        (["--env-file", str(env_file)], None),
        (["--format", "json"], env_file_values),
        ([], env_file_values),
    )

    last_error = ""
    for flags, env_override in attempts:
        compose_cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "config",
        ]
        compose_cmd.extend(flags)
        # normalize trailing None placeholder in older/newer flag combinations
        compose_cmd = [item for item in compose_cmd if item is not None]

        compose_env = None if env_override is None else {**os.environ, **env_override}
        result = subprocess.run(
            compose_cmd,
            check=False,
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=compose_env,
        )
        last_error = result.stderr
        if result.returncode == 0:
            return result.stdout

        if "unknown flag: --env-file" in result.stderr.lower():
            continue
        if "unknown option: --env-file" in result.stderr.lower():
            continue

        if "--format" in compose_cmd and (
            "unknown flag: --format" in result.stderr.lower()
            or "unknown shorthand flag: --format" in result.stderr.lower()
        ):
            # retry without JSON support using same env source on next candidates
            continue

        break

    raise RuntimeError(
        "Docker compose config failed for all fallback permutations.\n"
        f"Last stderr:\n{last_error}"
    )


def _coerce_compose_env(raw_env: object) -> dict[str, str]:
    env: dict[str, str] = {}
    if raw_env is None:
        return env
    if isinstance(raw_env, dict):
        for key, value in raw_env.items():
            env[str(key)] = "" if value is None else str(value)
        return env
    if isinstance(raw_env, list):
        for entry in raw_env:
            if not isinstance(entry, str):
                continue
            match = re.match(r"^([^=]+)=(.*)$", entry, re.DOTALL)
            if match:
                env[match.group(1)] = match.group(2)
        return env
    return env


def _parse_compose_env(rendered: str) -> dict[str, dict[str, str]]:
    def _get_service_env(data: object) -> dict[str, dict[str, str]]:
        services: dict[str, dict[str, str]] = {}
        if not isinstance(data, dict):
            return services
        for service_name, service_data in data.get("services", {}).items():
            if not isinstance(service_data, dict):
                continue
            services[service_name] = _coerce_compose_env(service_data.get("environment"))
        return services

    raw = rendered.lstrip()
    if raw.startswith("{"):
        try:
            compose_data = json.loads(raw)
            return _get_service_env(compose_data)
        except json.JSONDecodeError:
            pass
    return _parse_compose_env_text(rendered)


def _parse_compose_env_text(rendered: str) -> dict[str, dict[str, str]]:
    services: dict[str, dict[str, str]] = {}
    service_re = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
    env_header_re = re.compile(r"^    environment:\s*$")
    list_env_re = re.compile(r"^      -\s*([^=\s:]+)\s*=(.*)$")
    map_env_re = re.compile(r"^      ([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")

    current_service: str | None = None
    in_environment = False
    for raw_line in rendered.splitlines():
        service_match = service_re.match(raw_line)
        if service_match:
            current_service = service_match.group(1)
            in_environment = False
            continue

        if current_service and env_header_re.match(raw_line):
            in_environment = True
            services.setdefault(current_service, {})
            continue

        if in_environment:
            if not raw_line.startswith("      "):
                if raw_line.startswith("    "):
                    in_environment = False
                    current_service = None
                continue
            if current_service is None:
                continue

            if raw_line.startswith("      - "):
                entry_match = list_env_re.match(raw_line)
                if entry_match:
                    service_env = services.setdefault(current_service, {})
                    service_env[entry_match.group(1)] = entry_match.group(2).strip()
                continue
            entry_match = map_env_re.match(raw_line)
            if entry_match:
                service_env = services.setdefault(current_service, {})
                service_env[entry_match.group(1)] = entry_match.group(2).strip()
    return services


def _parse_compose_port_bindings(rendered: str) -> dict[str, list[str]]:
    services: dict[str, list[str]] = {}
    service_re = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
    ports_header_re = re.compile(r"^    ports:\s*$")
    ports_entry_re = re.compile(r"^      -\s*(.+)\s*$")

    current_service: str | None = None
    in_ports = False
    for raw_line in rendered.splitlines():
        service_match = service_re.match(raw_line)
        if service_match:
            current_service = service_match.group(1)
            in_ports = False
            continue

        if current_service and ports_header_re.match(raw_line):
            in_ports = True
            services.setdefault(current_service, [])
            continue

        if in_ports:
            if not raw_line.startswith("      "):
                if raw_line.startswith("    "):
                    in_ports = False
                    current_service = None
                continue
            if current_service is None:
                continue
            entry_match = ports_entry_re.match(raw_line)
            if entry_match:
                raw_entry = entry_match.group(1).strip().strip('"').strip("'")
                if raw_entry:
                    services.setdefault(current_service, []).append(raw_entry)
            continue

    return {name: entries for name, entries in services.items() if entries}


def _parse_compose_ports(rendered: str) -> dict[str, list[str]]:
    raw = rendered.lstrip()
    if raw.startswith("{"):
        try:
            compose_data = json.loads(raw)
            services = compose_data.get("services", {})
            if not isinstance(services, dict):
                return {}

            result: dict[str, list[str]] = {}
            for service_name, service_data in services.items():
                if not isinstance(service_data, dict):
                    continue
                service_ports = service_data.get("ports")
                if not isinstance(service_ports, list):
                    continue
                ports: list[str] = []
                for entry in service_ports:
                    if isinstance(entry, str):
                        ports.append(entry.strip())
                    elif isinstance(entry, dict):
                        target = str(entry.get("target", "")).strip()
                        published = str(entry.get("published", "")).strip()
                        host = str(
                            entry.get("host") if entry.get("host") is not None else entry.get("host_ip", "")
                        ).strip()
                        if host:
                            if published and target:
                                ports.append(f"{host}:{published}:{target}")
                            elif target:
                                ports.append(f"{host}:{target}")
                        elif published and target:
                            ports.append(f"{published}:{target}")
                if ports:
                    result[service_name] = ports
            return result
        except json.JSONDecodeError:
            pass

    return _parse_compose_port_bindings(rendered)


def _port_binding_is_loopback(bind_host: str) -> bool:
    host = bind_host.strip().lower()
    return host in {"127.0.0.1", "::1", "localhost"}


def _parse_host_from_port_binding(binding: str) -> str | None:
    value = binding.strip()
    if value.startswith("["):
        end = value.find("]")
        if end == -1:
            return None
        return value[1:end]
    if COMPOSE_SERVICE_PORT_RE.match(value):
        parts = value.split(":")
        if len(parts) == 2:
            host, _published_or_container = parts
            return None if host.isdigit() else host
        if len(parts) == 3:
            return parts[0]
        if len(parts) == 1:
            return None
        return parts[0]
    return None


def _require_loopback_backend_api_bind(
    scenario: str,
    services_env: dict[str, dict[str, str]],
    service_port_bindings: dict[str, list[str]],
) -> None:
    backend_env = services_env.get("backend-api", {})
    bind_host = backend_env.get("OKR_BACKEND_BIND_ADDRESS", "")
    if bind_host:
        if not _port_binding_is_loopback(bind_host):
            raise RuntimeError(
                f"backend-api for {scenario} has unsafe bind host {bind_host!r} via "
                "OKR_BACKEND_BIND_ADDRESS; expected loopback host."
            )

    saw_port_with_explicit_host = False

    for binding in service_port_bindings.get("backend-api", []):
        if not COMPOSE_SERVICE_PORT_RE.match(binding):
            continue
        host = _parse_host_from_port_binding(binding)
        if host is None:
            raise RuntimeError(
                f"backend-api for {scenario} exposes port binding '{binding}' without "
                "an explicit host; refuse production-like profile."
            )
        if not _port_binding_is_loopback(host):
            raise RuntimeError(
                f"backend-api for {scenario} binds public host {host!r} in compose port map; "
                f"expected 127.0.0.1/::1/localhost in binding {binding!r}."
            )
        saw_port_with_explicit_host = True


def _validate_k8s_backend_runtime_ingress() -> None:
    service_file = ROOT / "deploy" / "k8s" / "service-backend-api.yaml"
    deployment_file = ROOT / "deploy" / "k8s" / "deployment-backend-api.yaml"

    if not service_file.exists():
        raise RuntimeError("Kubernetes backend API service file missing.")
    if not deployment_file.exists():
        raise RuntimeError("Kubernetes backend API deployment file missing.")

    service_type_re = re.compile(r"^\s*type:\s*(\S+)\s*$")
    service_type: str | None = None
    for line in service_file.read_text(encoding="utf-8").splitlines():
        match = service_type_re.match(line)
        if match:
            service_type = match.group(1).strip()
            break
    if service_type and service_type.lower() != "clusterip":
        raise RuntimeError(
            f"Kubernetes backend service must be ClusterIP; found service type {service_type!r}."
        )

    deployment_lines = deployment_file.read_text(encoding="utf-8").splitlines()
    container_re = re.compile(r"^\s*-\s+name:\s*backend-api\s*$")
    env_header_re = re.compile(r"^\s*env:\s*$")
    env_name_re = re.compile(r"^\s*-\s+name:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$")
    env_value_re = re.compile(r"^\s*value:\s*(.+?)\s*$")
    env_valuefrom_re = re.compile(r"^\s*valueFrom:\s*$")
    container_indent: int | None = None

    container_start = None
    for index, line in enumerate(deployment_lines):
        if container_re.match(line):
            container_start = index
            container_indent = len(line) - len(line.lstrip())
            break
    if container_start is None:
        raise RuntimeError("Kubernetes backend-api container block is missing in deployment manifest.")
    if container_indent is None:
        raise RuntimeError("Kubernetes backend-api container block is malformed.")

    backend_container_lines: list[str] = []
    for follow in deployment_lines[container_start + 1 :]:
        if not follow.strip():
            continue
        follow_indent = len(follow) - len(follow.lstrip())
        if follow.lstrip().startswith("- name:") and follow_indent <= container_indent:
            break
        if follow_indent > container_indent:
            backend_container_lines.append(follow)

    in_env = False
    env_values: dict[str, str] = {}
    env_refs: set[str] = set()
    required_boolean = {
        "OKR_BACKEND_ENFORCE_TOKEN": "true",
        "OKR_BACKEND_ENFORCE_REQUEST_SIGNING": "true",
    }
    required_present = {
        "OKR_BACKEND_SERVICE_TOKEN",
        "OKR_BACKEND_SIGNING_SECRET",
        "OKR_BACKEND_SECURITY_STATE_BACKEND",
    }
    current_env: str | None = None
    for line in backend_container_lines:
        if env_header_re.match(line):
            in_env = True
            current_env = None
            continue

        if in_env:
            name_match = env_name_re.match(line)
            if name_match:
                current_env = name_match.group(1)
                continue
            if current_env:
                value_match = env_value_re.match(line)
                if value_match:
                    env_values[current_env] = value_match.group(1).strip().strip('"').strip("'")
                    current_env = None
                    continue
                if env_valuefrom_re.match(line):
                    env_refs.add(current_env)
                    current_env = None
                    continue

    for key, expected in required_boolean.items():
        value = env_values.get(key, "").strip().lower()
        if value != expected:
            raise RuntimeError(
                f"Kubernetes backend deployment missing secure runtime bool: {key} must be {expected!r}, got {value!r}."
            )

    for key in required_present:
        if key not in env_values and key not in env_refs:
            raise RuntimeError(
                f"Kubernetes backend deployment does not expose {key} in container env."
            )

    state_backend = env_values.get("OKR_BACKEND_SECURITY_STATE_BACKEND", "database").lower().strip()
    if state_backend not in {"database", "redis"}:
        raise RuntimeError(
            "Kubernetes backend deployment requires OKR_BACKEND_SECURITY_STATE_BACKEND "
            "to be database or redis."
        )


def _require_compose_env_value(
    services_env: dict[str, dict[str, str]],
    scenario: str,
    service: str,
    key: str,
    expected: str,
) -> None:
    service_env = services_env.get(service, {})
    observed = service_env.get(key)
    if observed != expected:
        raise RuntimeError(
            f"{service} for {scenario} missing expected {key}: "
            f"expected {expected!r}, got {observed!r}."
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

    compose_file = ROOT / "deploy" / "docker" / "docker-compose.yml"

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
                rendered = _run_compose_config(env_file, compose_file)
                compose_output.write_text(rendered, encoding="utf-8")

                services_env = _parse_compose_env(rendered)
                if not services_env:
                    raise RuntimeError(
                        "Compose expansion did not produce a JSON service env map for "
                        f"{scenario.name}. This indicates a compose output format incompatibility."
                    )

                token = "runtime-smoke-token-please-change-2026-ci"
                bff_secret = "runtime-smoke-bff-session-secret-very-long"
                _require_compose_env_value(
                    services_env,
                    scenario.name,
                    "backend-api",
                    "OKR_BACKEND_SERVICE_TOKEN",
                    token,
                )
                _require_compose_env_value(
                    services_env,
                    scenario.name,
                    "backend-worker",
                    "OKR_BACKEND_SERVICE_TOKEN",
                    token,
                )
                _require_compose_env_value(
                    services_env,
                    scenario.name,
                    "spa-bff",
                    "OKR_BACKEND_SERVICE_TOKEN",
                    token,
                )
                _require_compose_env_value(
                    services_env,
                    scenario.name,
                    "spa-bff",
                    "BFF_SESSION_SECRET",
                    bff_secret,
                )
                backend_port_bindings = _parse_compose_ports(rendered)
                _require_loopback_backend_api_bind(
                    scenario.name,
                    services_env,
                    backend_port_bindings,
                )

        _validate_k8s_backend_runtime_ingress()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    run_matrix(require_docker=args.require_docker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
