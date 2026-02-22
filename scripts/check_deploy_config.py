#!/usr/bin/env python3
"""Validate deploy configuration templates/runtime for secure defaults."""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ENV_KEYS = (
    "OKR_DATABASE_URL",
    "OKR_BACKEND_API_URL",
    "OKR_BACKEND_SERVICE_TOKEN",
    "OKR_BACKEND_SIGNING_SECRET",
    "OKR_BOOTSTRAP_ADMIN_PASSWORD",
    "OKR_BACKEND_PROXY_MUTATIONS",
    "OKR_ALLOW_LOCAL_BACKEND_FALLBACK",
    "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN",
    "OKR_ENFORCE_STRONG_PASSWORD_POLICY",
    "PDF_METHOD",
    "PDFSHIFT_API_KEY",
    "OKR_STRICT_RUNTIME_PREFLIGHT",
)

SECURE_EXPECTED = {
    "OKR_BACKEND_PROXY_MUTATIONS": "true",
    "OKR_ALLOW_LOCAL_BACKEND_FALLBACK": "false",
    "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN": "false",
    "OKR_ENFORCE_STRONG_PASSWORD_POLICY": "true",
    "PDF_METHOD": "pdfshift",
    "OKR_STRICT_RUNTIME_PREFLIGHT": "true",
}

PLACEHOLDER_TOKENS = (
    "CHANGE_ME",
    "PROJECT_REF",
    "DB_PASSWORD",
    "YOUR-",
    "YOUR_",
    "EXAMPLE",
    "REPLACE_ME",
)


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


def _looks_placeholder(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    if raw.startswith("<") and raw.endswith(">"):
        return True
    upper = raw.upper()
    return any(token in upper for token in PLACEHOLDER_TOKENS)


def _parse_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _load_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        payload = tomllib.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("Top-level TOML payload must be a table/object.")
    return payload


def _secret_value(secrets: dict, *names: str) -> str:
    for name in names:
        if name in secrets and secrets[name] is not None:
            return str(secrets[name]).strip()
    return ""


def _secret_database_url(secrets: dict) -> str:
    db_section = secrets.get("database", {})
    if not hasattr(db_section, "get"):
        return ""
    value = db_section.get("url")
    return str(value).strip() if value is not None else ""


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


def validate(
    *,
    env_file: Path,
    secrets_file: Path,
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

    secrets: dict = {}
    if secrets_file.exists():
        try:
            secrets = _load_toml(secrets_file)
        except Exception as exc:
            report.errors.append(
                f"Failed reading TOML file {_display_path(secrets_file)}: {exc}"
            )
            return report
    elif mode == "template":
        report.errors.append(f"Missing secrets template: {_display_path(secrets_file)}")
    else:
        report.warnings.append(f"Secrets file not found: {_display_path(secrets_file)}")

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

    _validate_database_url(
        env.get("OKR_DATABASE_URL", ""),
        report,
        strict=(mode == "runtime"),
    )

    if secrets:
        if "pdfshift_api_key" not in secrets:
            report.errors.append(
                "Missing 'pdfshift_api_key' in secrets TOML root table."
            )
        secret_pdf_method = _normalize(_secret_value(secrets, "PDF_METHOD", "pdf_method"))
        if secret_pdf_method and secret_pdf_method != "pdfshift":
            report.errors.append(
                f"Secrets PDF method must be 'pdfshift', found '{secret_pdf_method}'."
            )

        if "database" not in secrets:
            report.errors.append("Missing '[database]' table in secrets TOML.")
        elif not _secret_database_url(secrets):
            report.errors.append("Missing 'database.url' value in secrets TOML.")

    if mode == "runtime":
        required_runtime_keys = (
            "OKR_DATABASE_URL",
            "OKR_BACKEND_SERVICE_TOKEN",
            "OKR_BACKEND_SIGNING_SECRET",
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

        pdf_env = env.get("PDFSHIFT_API_KEY", "")
        pdf_secret = _secret_value(secrets, "pdfshift_api_key", "PDFSHIFT_API_KEY")
        provided_values = [v for v in [pdf_env, pdf_secret] if str(v).strip()]
        if not provided_values:
            report.errors.append(
                "PDFShift API key is missing in both env and secrets runtime config."
            )
        elif all(_looks_placeholder(v) for v in provided_values):
            report.errors.append(
                "PDFShift API key appears to be a placeholder in runtime mode."
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
        "--secrets-file",
        type=Path,
        default=ROOT / "deploy" / "secrets" / "secrets.toml.example",
        help="Path to Streamlit secrets TOML file.",
    )
    parser.add_argument(
        "--mode",
        choices=("template", "runtime"),
        default="template",
        help="Validation mode: template (for CI) or runtime (for go-live checks).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    report = validate(
        env_file=args.env_file.resolve(),
        secrets_file=args.secrets_file.resolve(),
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
