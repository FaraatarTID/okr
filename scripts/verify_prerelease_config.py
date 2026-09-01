#!/usr/bin/env python3
"""Validate the disposable, synthetic Darkube pre-release configuration."""

from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from scripts.check_deploy_config import (
    ROOT,
    ValidationReport,
    _looks_placeholder,
    _parse_dotenv,
    validate as validate_deploy_config,
)


DEFAULT_ENV_FILE = ROOT / "deploy" / "darkube" / "prerelease" / ".env.example"

EXPECTED_VALUES = {
    "OKR_DEPLOYMENT_PROFILE": "single_tenant_saas",
    "OKR_SAAS_MODE": "true",
    "OKR_DATA_ACCESS_MODE": "database",
    "OKR_ENVIRONMENT_ID": "okr-prerelease",
    "OKR_CUSTOMER_ID": "synthetic-prerelease",
    "OKR_BACKUP_PROVIDER": "deferred",
    "OKR_BACKUP_SCHEDULE": "deferred",
    "OKR_BACKEND_SECURITY_STATE_BACKEND": "database",
    "PDF_METHOD": "chromium",
    "ALLOW_EXTERNAL_AI": "false",
}

SUPABASE_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
)

PROVIDER_CREDENTIAL_KEYS = {
    "HAMRAVESH_API_TOKEN",
    "HAMRAVESH_TOKEN",
    "HAMRAVESH_ACCESS_KEY",
    "HAMRAVESH_SECRET_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "KUBECONFIG",
    "KUBE_CONFIG_DATA",
}

SECRET_KEYS = (
    "OKR_BACKEND_SERVICE_TOKEN",
    "OKR_BACKEND_SIGNING_SECRET",
    "BFF_SESSION_SECRET",
    "OKR_BOOTSTRAP_ADMIN_PASSWORD",
)

NON_PRODUCTION_MARKERS = {
    "prod",
    "production",
    "live",
    "customer",
    "customers",
}

PRIVATE_DNS_SUFFIXES = (
    ".internal",
    ".intranet",
    ".lan",
    ".local",
    ".svc",
    ".cluster.local",
)

PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "fd00::/8",
        "fe80::/10",
    )
)


def _normalize(value: object) -> str:
    return str(value or "").strip().lower()


def _is_empty(value: object) -> bool:
    return not str(value or "").strip()


def _has_production_marker(value: object) -> bool:
    normalized = _normalize(value).replace("_", "-")
    parts = {part for part in normalized.replace(".", "-").split("-") if part}
    return bool(parts & NON_PRODUCTION_MARKERS)


def _validate_private_database_url(
    value: object, report: ValidationReport, *, runtime: bool
) -> None:
    raw = str(value or "").strip()
    if not raw.startswith("postgresql+psycopg2://"):
        return

    parsed = urlparse(raw)
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return
    if "supabase" in host:
        report.errors.append(
            "OKR_DATABASE_URL must not use a Supabase host in Darkube pre-release."
        )
        return

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if not any(address in network for network in PRIVATE_NETWORKS):
            report.errors.append(
                "OKR_DATABASE_URL must use a private database host in Darkube pre-release."
            )
        return

    if "." not in host or any(host.endswith(suffix) for suffix in PRIVATE_DNS_SUFFIXES):
        return
    if runtime:
        report.errors.append(
            "OKR_DATABASE_URL must use a private/internal database hostname in runtime mode."
        )


def validate_prerelease_config(
    env: Mapping[str, str], *, runtime: bool = False
) -> ValidationReport:
    """Validate pre-release invariants on top of the shared config contract."""

    report = ValidationReport()

    for key, expected in EXPECTED_VALUES.items():
        actual = _normalize(env.get(key, ""))
        if actual != expected:
            report.errors.append(
                f"{key} must be '{expected}' for the Darkube pre-release environment."
            )

    for key in SUPABASE_KEYS:
        if not _is_empty(env.get(key)):
            report.errors.append(
                f"{key} must be empty; Supabase fallback is disabled for pre-release."
            )

    _validate_private_database_url(
        env.get("OKR_DATABASE_URL", ""), report, runtime=runtime
    )

    for key in ("OKR_ENV", "OKR_RUNTIME_ENV"):
        if _has_production_marker(env.get(key, "")):
            report.errors.append(
                f"{key} must identify a non-production pre-release runtime."
            )

    for key in ("OKR_ENVIRONMENT_ID", "OKR_CUSTOMER_ID"):
        if _has_production_marker(env.get(key, "")):
            report.errors.append(
                f"{key} must not identify a production or live customer environment."
            )

    for key in PROVIDER_CREDENTIAL_KEYS:
        if not _is_empty(env.get(key)):
            report.errors.append(
                f"Provider credential {key} is not allowed in the synthetic-only "
                "pre-release configuration."
            )

    if not _is_empty(env.get("PDFSHIFT_API_KEY")):
        report.errors.append(
            "PDFSHIFT_API_KEY must be empty because pre-release uses local Chromium PDF generation."
        )
    for key in ("GEMINI_API_KEY", "AI_API_KEY"):
        if not _is_empty(env.get(key)):
            report.errors.append(
                f"{key} must be empty in the synthetic-only pre-release configuration."
            )

    if runtime:
        for key in SECRET_KEYS:
            value = str(env.get(key, "")).strip()
            if not value:
                report.errors.append(f"{key} is required in pre-release runtime mode.")
            elif _looks_placeholder(value) or "generate_in_darkube" in value.lower():
                report.errors.append(
                    f"{key} still contains a template placeholder in runtime mode."
                )
        session_secret = str(env.get("BFF_SESSION_SECRET", "")).strip()
        if session_secret and len(session_secret) < 32:
            report.errors.append(
                "BFF_SESSION_SECRET must be at least 32 characters in runtime mode."
            )

    return report


def validate_prerelease_file(
    env_file: Path, *, runtime: bool = False
) -> ValidationReport:
    """Run the shared deploy validator and then the pre-release policy checks."""

    report = validate_deploy_config(
        env_file=env_file.resolve(), mode="runtime" if runtime else "template"
    )
    if not env_file.exists():
        return report
    try:
        env = _parse_dotenv(env_file.resolve())
    except Exception as exc:
        report.errors.append(f"Failed reading pre-release env file: {exc}")
        return report

    prerelease_report = validate_prerelease_config(env, runtime=runtime)
    report.errors.extend(prerelease_report.errors)
    report.warnings.extend(prerelease_report.warnings)
    return report


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the synthetic-only Darkube pre-release configuration."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Path to the pre-release dotenv file.",
    )
    parser.add_argument(
        "--mode",
        choices=("template", "runtime"),
        default="template",
        help="Validate a template or a populated runtime configuration.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    report = validate_prerelease_file(args.env_file, runtime=args.mode == "runtime")
    for warning in report.warnings:
        print(f"WARN: {warning}")
    if not report.ok:
        print(f"Pre-release config check failed (mode={args.mode}).")
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"Pre-release config check passed (mode={args.mode}) "
        f"with {len(report.warnings)} warning(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
