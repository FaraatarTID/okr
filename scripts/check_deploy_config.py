#!/usr/bin/env python3
"""Validate deploy configuration templates/runtime for secure defaults."""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

# Make direct `python scripts/check_deploy_config.py` execution behave like
# module execution in CI and local shells.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.saas.environment_config import ConfigError, SaaSEnvironmentConfig  # noqa: E402


REQUIRED_ENV_KEYS = (
    "OKR_DATABASE_URL",
    "OKR_BACKEND_API_URL",
    "OKR_BACKEND_SERVICE_TOKEN",
    "OKR_BACKEND_SIGNING_SECRET",
    "BFF_COOKIE_SECURE",
    "OKR_BOOTSTRAP_ADMIN_PASSWORD",
    "OKR_BACKEND_ENFORCE_REQUEST_SIGNING",
    "OKR_BACKEND_PROXY_MUTATIONS",
    "OKR_BACKEND_PROXY_READS",
    "OKR_BACKEND_SECURITY_STATE_BACKEND",
    "OKR_BACKEND_BIND_ADDRESS",
    "OKR_ALLOW_LOCAL_MUTATION_FALLBACK",
    "OKR_ALLOW_LOCAL_READ_FALLBACK",
    "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN",
    "OKR_ENFORCE_STRONG_PASSWORD_POLICY",
    "PDF_METHOD",
    "OKR_STRICT_RUNTIME_PREFLIGHT",
)

SECURE_EXPECTED = {
    "BFF_COOKIE_SECURE": "true",
    "OKR_BACKEND_ENFORCE_REQUEST_SIGNING": "true",
    "OKR_BACKEND_PROXY_MUTATIONS": "true",
    "OKR_BACKEND_PROXY_READS": "true",
    "OKR_ALLOW_LOCAL_MUTATION_FALLBACK": "false",
    "OKR_ALLOW_LOCAL_READ_FALLBACK": "false",
    "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN": "false",
    "OKR_ENFORCE_STRONG_PASSWORD_POLICY": "true",
    "OKR_STRICT_RUNTIME_PREFLIGHT": "true",
}

ALLOWED_SECURITY_STATE_BACKENDS = {"database", "redis"}
ALLOWED_PDF_METHODS = {"pdfshift", "chromium"}

PLACEHOLDER_TOKENS = (
    "CHANGE_ME",
    "PROJECT_REF",
    "DB_PASSWORD",
    "YOUR-",
    "YOUR_",
    "EXAMPLE",
    "REPLACE_ME",
)

_PRIVATE_DNS_SUFFIXES = (
    ".svc",
    ".svc.cluster.local",
    ".cluster.local",
    ".local",
    ".internal",
    ".intranet",
    ".lan",
    ".home",
)

_PRIVATE_V4_NETWORKS = tuple(
    map(
        ipaddress.ip_network,
        (
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "169.254.0.0/16",
        ),
    )
)

_PRIVATE_V6_NETWORKS = tuple(map(ipaddress.ip_network, ("fd00::/8", "fe80::/10")))


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except Exception:
        return str(path)


def _normalize(value: str) -> str:
    return str(value or "").strip().lower()


def is_saas_mode_requested(value: str) -> bool:
    """Return whether a deployment explicitly requests SaaS mode."""

    return _normalize(value) in {"1", "true", "yes", "on"}


def _looks_placeholder(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    if raw.startswith("<") and raw.endswith(">"):
        return True
    upper = raw.upper()
    return any(token in upper for token in PLACEHOLDER_TOKENS)


def _normalize_pdf_method(value: str) -> str:
    method = _normalize(value)
    if method == "shiftpdf":
        return "pdfshift"
    if method in {"chrome", "playwright"}:
        return "chromium"
    return method


def _parse_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _validate_database_url(url: str, report: ValidationReport, *, strict: bool) -> None:
    raw = str(url or "").strip()
    if not raw:
        if strict:
            report.errors.append("OKR_DATABASE_URL is required and cannot be empty.")
        return

    if not raw.startswith("postgresql+psycopg2://"):
        report.errors.append(
            "OKR_DATABASE_URL must start with 'postgresql+psycopg2://'."
        )
        return

    parsed = urlparse(raw)
    if not parsed.hostname:
        report.errors.append("OKR_DATABASE_URL must include a database host.")
        return

    # Deployment policy: prefer Supabase transaction pooler in production paths.
    if ".pooler.supabase.com" not in raw or ":6543" not in raw:
        report.warnings.append(
            "OKR_DATABASE_URL is not using the expected Supabase transaction pooler (:6543)."
        )


def _validate_redis_url(url: str, report: ValidationReport, *, strict: bool) -> None:
    raw = str(url or "").strip()
    if not raw:
        report.errors.append(
            "OKR_BACKEND_SECURITY_STATE_REDIS_URL is required when "
            "OKR_BACKEND_SECURITY_STATE_BACKEND=redis."
        )
        return

    if not raw.startswith(("redis://", "rediss://")):
        report.errors.append(
            "OKR_BACKEND_SECURITY_STATE_REDIS_URL must start with 'redis://' or 'rediss://'."
        )
        return

    parsed = urlparse(raw)
    if not parsed.hostname:
        report.errors.append(
            "OKR_BACKEND_SECURITY_STATE_REDIS_URL must include a Redis host."
        )
        return

    if strict and _looks_placeholder(raw):
        report.errors.append(
            "OKR_BACKEND_SECURITY_STATE_REDIS_URL appears to be a placeholder in runtime mode."
        )


def _validate_backend_bind_address(value: str, report: ValidationReport) -> None:
    raw = str(value or "").strip()
    if not raw:
        report.errors.append("OKR_BACKEND_BIND_ADDRESS cannot be empty.")
        return
    if _normalize(raw) not in {"127.0.0.1", "localhost", "::1"}:
        report.errors.append(
            "OKR_BACKEND_BIND_ADDRESS must remain loopback/private "
            "(127.0.0.1, localhost, or ::1)."
        )


def _validate_backend_api_url(
    raw_url: str, report: ValidationReport, *, strict: bool
) -> None:
    value = str(raw_url or "").strip()
    if not value:
        report.errors.append("OKR_BACKEND_API_URL cannot be empty.")
        return

    parsed = urlparse(value)
    if not parsed.scheme or parsed.scheme not in {"http", "https"}:
        report.errors.append("OKR_BACKEND_API_URL must use http:// or https:// scheme.")
        return
    if not parsed.hostname:
        report.errors.append("OKR_BACKEND_API_URL must include a hostname.")
        return

    host = str(parsed.hostname).strip().lower()
    if host in {"0.0.0.0", "localhost", "127.0.0.1", "::1"}:
        if strict:
            report.errors.append(
                "OKR_BACKEND_API_URL must not use loopback for production runtime."
            )
        return

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if (
            ip.version == 4 and any(ip in network for network in _PRIVATE_V4_NETWORKS)
        ) or (
            ip.version == 6
            and (
                ip.is_loopback or any(ip in network for network in _PRIVATE_V6_NETWORKS)
            )
        ):
            return
        report.errors.append(
            "OKR_BACKEND_API_URL must not point to a public IP in runtime mode."
        )
        return

    if host.count(".") == 0:
        return
    if host in {"backend-api", "backend", "backend-service", "okr-backend-api"}:
        return
    if any(host.endswith(suffix) for suffix in _PRIVATE_DNS_SUFFIXES):
        return
    if "backend-api" in host and ".svc" in host:
        return

    if strict:
        report.errors.append(
            f"OKR_BACKEND_API_URL hostname '{host}' appears non-private. "
            "Use an internal service hostname (for example backend-api or a service "
            "DNS name such as backend-api.ns.svc.cluster.local)."
        )


def validate_saas_environment(
    env: Mapping[str, str], *, runtime: bool = False, required: bool = False
) -> ValidationReport:
    """Validate the dedicated SaaS contract without changing self-hosted rules."""

    report = ValidationReport()
    profile = _normalize(env.get("OKR_DEPLOYMENT_PROFILE", ""))
    saas_requested = is_saas_mode_requested(env.get("OKR_SAAS_MODE", ""))
    if not required and not saas_requested and profile != "single_tenant_saas":
        return report

    try:
        SaaSEnvironmentConfig.from_env(env)
    except ConfigError as exc:
        report.errors.append(str(exc))
        return report

    if runtime:
        for key in ("OKR_ENVIRONMENT_ID", "OKR_CUSTOMER_ID", "OKR_DATABASE_URL"):
            if _looks_placeholder(env.get(key, "")):
                report.errors.append(
                    f"'{key}' appears to be a placeholder in SaaS runtime mode."
                )
    return report


def validate(
    *,
    env_file: Path,
    mode: str,
) -> ValidationReport:
    report = ValidationReport()

    if not env_file.exists():
        report.errors.append(f"Missing env file: {_display_path(env_file)}")
        return report

    try:
        env = _parse_dotenv(env_file)
    except Exception as exc:
        report.errors.append(
            f"Failed reading env file {_display_path(env_file)}: {exc}"
        )
        return report

    for key in REQUIRED_ENV_KEYS:
        if key not in env:
            report.errors.append(
                f"Missing required key '{key}' in {_display_path(env_file)}."
            )

    for key, expected in SECURE_EXPECTED.items():
        actual = _normalize(env.get(key, ""))
        if not actual:
            report.errors.append(
                f"Missing value for '{key}' in {_display_path(env_file)}."
            )
            continue
        if actual != expected:
            report.errors.append(
                f"'{key}' must be '{expected}', found '{env.get(key, '')}'."
            )

    pdf_method = _normalize_pdf_method(env.get("PDF_METHOD", ""))
    if not pdf_method:
        report.errors.append(
            f"Missing value for 'PDF_METHOD' in {_display_path(env_file)}."
        )
    elif pdf_method not in ALLOWED_PDF_METHODS:
        report.errors.append(
            f"'PDF_METHOD' must be one of: {', '.join(sorted(ALLOWED_PDF_METHODS))}; "
            f"found '{env.get('PDF_METHOD', '')}'."
        )

    _validate_database_url(
        env.get("OKR_DATABASE_URL", ""),
        report,
        strict=(mode == "runtime"),
    )

    security_state_backend = _normalize(
        env.get("OKR_BACKEND_SECURITY_STATE_BACKEND", "")
    )
    if not security_state_backend:
        report.errors.append(
            "Missing value for 'OKR_BACKEND_SECURITY_STATE_BACKEND' "
            f"in {_display_path(env_file)}."
        )
    elif security_state_backend not in ALLOWED_SECURITY_STATE_BACKENDS:
        report.errors.append(
            "OKR_BACKEND_SECURITY_STATE_BACKEND must be one of: database, redis."
        )
    elif security_state_backend == "redis":
        _validate_redis_url(
            env.get("OKR_BACKEND_SECURITY_STATE_REDIS_URL", ""),
            report,
            strict=(mode == "runtime"),
        )

    _validate_backend_bind_address(env.get("OKR_BACKEND_BIND_ADDRESS", ""), report)
    _validate_backend_api_url(
        env.get("OKR_BACKEND_API_URL", ""),
        report,
        strict=(mode == "runtime"),
    )

    report.errors.extend(
        validate_saas_environment(env, runtime=(mode == "runtime")).errors
    )

    if mode == "runtime":
        required_runtime_keys = (
            "OKR_DATABASE_URL",
            "OKR_BACKEND_SERVICE_TOKEN",
            "OKR_BACKEND_SIGNING_SECRET",
            "BFF_SESSION_SECRET",
            "OKR_BOOTSTRAP_ADMIN_PASSWORD",
        )
        for key in required_runtime_keys:
            value = env.get(key, "")
            if not str(value).strip():
                report.errors.append(f"'{key}' cannot be empty in runtime mode.")
                continue
            if _looks_placeholder(value):
                report.errors.append(
                    f"'{key}' appears to be a placeholder in runtime mode."
                )
            elif key == "BFF_SESSION_SECRET" and len(str(value).strip()) < 32:
                report.errors.append(
                    "'BFF_SESSION_SECRET' must be at least 32 characters in runtime mode."
                )

        if pdf_method == "pdfshift":
            pdf_env = env.get("PDFSHIFT_API_KEY", "")
            if not str(pdf_env).strip():
                report.errors.append(
                    "PDFSHIFT_API_KEY is missing in env runtime config."
                )
            elif _looks_placeholder(pdf_env):
                report.errors.append(
                    "PDFSHIFT_API_KEY appears to be a placeholder in runtime mode."
                )

    return report


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate deploy configuration files for secure defaults."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / "deploy" / "docker" / ".env.example",
        help="Path to dotenv file (default: deploy/docker/.env.example).",
    )
    parser.add_argument(
        "--mode",
        choices=("template", "runtime"),
        default="template",
        help="Validation mode: template (for CI) or runtime (for go-live checks).",
    )
    parser.add_argument(
        "--environment",
        action="store_true",
        help="Validate the current process environment instead of a dotenv file.",
    )
    parser.add_argument(
        "--saas-only",
        action="store_true",
        help="Require and validate the SaaS environment contract.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.environment:
        report = validate_saas_environment(
            dict(os.environ), runtime=(args.mode == "runtime"), required=args.saas_only
        )
    elif args.saas_only:
        try:
            env = _parse_dotenv(args.env_file.resolve())
            report = validate_saas_environment(
                env, runtime=(args.mode == "runtime"), required=True
            )
        except Exception as exc:
            report = ValidationReport(errors=[f"Failed reading env file: {exc}"])
    else:
        report = validate(
            env_file=args.env_file.resolve(),
            mode=args.mode,
        )

    if report.warnings:
        for warning in report.warnings:
            print(f"WARN: {warning}")

    if not report.ok:
        print(f"Deploy config check failed (mode={args.mode}).")
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1

    print(
        f"Deploy config check passed (mode={args.mode}) "
        f"with {len(report.warnings)} warning(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
