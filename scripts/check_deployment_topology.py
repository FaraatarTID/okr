#!/usr/bin/env python3
"""Validate the provider-neutral four-service deployment topology."""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPOSE_FILE = ROOT / "deploy" / "docker" / "docker-compose.yml"
REQUIRED_SERVICES = ("spa-web", "spa-bff", "backend-api", "backend-worker")
PRIVATE_SERVICES = ("backend-api", "backend-worker", "postgres")
_SERVICE_HEADER = re.compile(r"^  ([A-Za-z0-9][A-Za-z0-9_.-]*):\s*$")
_FIELD_HEADER = re.compile(r"^    ([A-Za-z0-9][A-Za-z0-9_.-]*):\s*$")
_ENV_ENTRY = re.compile(r"^\s*-\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


class TopologyError(ValueError):
    """Raised when a deployment topology violates the service boundary."""


def _service_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    in_services = False
    current: str | None = None
    for line in text.splitlines():
        if line == "services:":
            in_services = True
            continue
        if in_services and line and not line.startswith(" "):
            break
        if not in_services:
            continue
        match = _SERVICE_HEADER.match(line)
        if match:
            current = match.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return blocks


def _section_lines(block: list[str], field: str) -> list[str]:
    header = f"    {field}:"
    selected: list[str] = []
    active = False
    for line in block:
        if line == header:
            active = True
            continue
        if active and _FIELD_HEADER.match(line):
            break
        if active:
            selected.append(line)
    return selected


def _environment(block: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _section_lines(block, "environment"):
        match = _ENV_ENTRY.match(line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    return values


def _dependencies(block: list[str]) -> set[str]:
    names: set[str] = set()
    for line in _section_lines(block, "depends_on"):
        match = re.match(r"^\s{6}([A-Za-z0-9][A-Za-z0-9_.-]*):", line)
        if match:
            names.add(match.group(1))
        match = re.match(r"^\s{6}-\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", line)
        if match:
            names.add(match.group(1))
    return names


def _default_interpolation(value: str) -> str | None:
    match = re.fullmatch(r"\$\{[^}:]+:-([^}]+)\}", value)
    if match:
        return match.group(1)
    return None


def _published_host(port_value: str) -> str | None:
    value = port_value.strip().strip('"').strip("'")
    value = re.sub(
        r"\$\{[^{}:]+:-([^{}]+)\}",
        lambda match: match.group(1),
        value,
    )
    if "${" in value:
        return None
    if value.startswith("["):
        closing = value.find("]")
        return value[1:closing] if closing >= 0 else None
    parts = value.split(":")
    if len(parts) < 2:
        return "0.0.0.0"
    return parts[0] or "0.0.0.0"


def _is_private_host(host: str) -> bool:
    normalized = host.strip().lower().rstrip(".")
    if normalized in {"localhost", "::1"} or normalized.endswith(".svc") or ".svc." in normalized:
        return True
    try:
        return ipaddress.ip_address(normalized).is_private or ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_compose_text(text: str) -> None:
    blocks = _service_blocks(text)
    missing = [name for name in REQUIRED_SERVICES if name not in blocks]
    if missing:
        raise TopologyError(f"missing required services: {', '.join(missing)}")
    if "postgres" not in blocks:
        raise TopologyError("missing required database service: postgres")

    expected_dependencies = {
        "backend-api": {"postgres"},
        "backend-worker": {"backend-api", "postgres"},
        "spa-bff": {"backend-api"},
        "spa-web": {"spa-bff"},
    }
    for service, dependencies in expected_dependencies.items():
        observed = _dependencies(blocks[service])
        missing_dependencies = dependencies - observed
        if missing_dependencies:
            raise TopologyError(
                f"{service} must depend on: {', '.join(sorted(missing_dependencies))}"
            )

    for service in PRIVATE_SERVICES:
        block = blocks[service]
        if any(line.strip().startswith("network_mode: host") for line in block):
            raise TopologyError(f"{service} must not use host networking")
        for line in _section_lines(block, "ports"):
            if not line.strip().startswith("-"):
                continue
            raw_value = line.split("-", 1)[1].strip()
            host = _published_host(raw_value)
            if host is None:
                raise TopologyError(f"{service} has an ambiguous published port: {raw_value}")
            if not _is_private_host(host):
                raise TopologyError(
                    f"{service} published port binds to public host '{host}'; "
                    "use no published port or an explicit private/loopback binding"
                )

    bff_env = _environment(blocks["spa-bff"])
    backend_url = bff_env.get("OKR_BACKEND_API_URL", "")
    if backend_url.startswith("${"):
        backend_url = _default_interpolation(backend_url) or ""
    parsed = urlsplit(backend_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"backend-api", "backend"} and not (parsed.hostname or "").endswith(".svc"):
        raise TopologyError(
            "spa-bff OKR_BACKEND_API_URL must target the private backend service"
        )


def validate_compose_file(path: Path) -> None:
    try:
        validate_compose_text(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TopologyError(f"cannot read compose file {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    args = parser.parse_args(argv)
    try:
        validate_compose_file(args.compose_file)
    except TopologyError as exc:
        print(f"[TOPOLOGY] deployment topology check failed: {exc}", file=sys.stderr)
        return 1
    print(
        "[TOPOLOGY] deployment topology passed: spa-web, spa-bff, "
        "backend-api, backend-worker; backend/database ingress private"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
