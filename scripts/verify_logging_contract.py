#!/usr/bin/env python3
"""Verify structured, secret-safe stdout/stderr logging contracts."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


class LoggingContractError(ValueError):
    """Raised when a runtime logging contract is not satisfied."""


BACKEND_FILES = (
    "src/observability_metrics.py",
    "backend_app/observability_http.py",
    "backend_app/worker.py",
)
AUDIT_FILE = "src/audit.py"
BFF_FILE = "spa-bff/src/server.ts"
FORBIDDEN_LOG_TERMS = (
    "password",
    "authorization",
    "session_secret",
    "signing_secret",
    "service_token",
)
BFF_FORBIDDEN_LOG_TERMS = FORBIDDEN_LOG_TERMS + (
    "request.headers",
    "request.body",
    "request.cookies",
)


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise LoggingContractError(f"missing logging surface: {relative}")
    return path.read_text(encoding="utf-8")


def _python_contract(root: Path) -> list[str]:
    errors: list[str] = []
    audit = _read(root, AUDIT_FILE)
    if "logging.FileHandler" in audit:
        errors.append(f"{AUDIT_FILE} must not use FileHandler")
    if "logging.StreamHandler(sys.stdout)" not in audit:
        errors.append(f"{AUDIT_FILE} must emit audit events to stdout")
    if "logging.StreamHandler(sys.stderr)" not in audit:
        errors.append(f"{AUDIT_FILE} must emit errors to stderr")
    if "redact_observability" not in audit:
        errors.append(f"{AUDIT_FILE} must apply centralized observability redaction")
    metrics = _read(root, BACKEND_FILES[0])
    if "redact_observability" not in metrics:
        errors.append(f"{BACKEND_FILES[0]} must apply centralized observability redaction")
    try:
        tree = ast.parse(metrics)
    except SyntaxError as exc:
        return [f"{BACKEND_FILES[0]} is not valid Python: {exc}"]

    log_payload = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "log_payload"
        ),
        None,
    )
    if log_payload is None:
        errors.append("backend log_payload function is missing")
    else:
        function_text = ast.get_source_segment(metrics, log_payload) or ""
        if "json.dumps" not in function_text:
            errors.append("backend log_payload must serialize JSON")
        for field in ("event", "ts"):
            if field not in function_text:
                errors.append(f"backend log_payload must include {field}")

    for relative in BACKEND_FILES[1:]:
        content = _read(root, relative)
        if "build_observability_log_payload" not in content:
            errors.append(f"{relative} must use structured observability payloads")
        for term in FORBIDDEN_LOG_TERMS:
            if term in content:
                errors.append(f"{relative} contains forbidden raw log input: {term}")
    return errors


def _bff_contract(root: Path) -> list[str]:
    errors: list[str] = []
    content = _read(root, BFF_FILE)
    if "Fastify({" not in content or "logger:" not in content:
        errors.append("BFF must configure Fastify logging to stdout/stderr")
    start = content.find("function buildBffLogPayload")
    end = content.find("\ntype BffRequestState", start)
    helper = content[start:end] if start >= 0 and end >= 0 else ""
    if not helper:
        errors.append("BFF structured log payload helper is missing")
    for field in ("event", "ts"):
        if field not in helper:
            errors.append(f"BFF log payload must include {field}")
    for term in BFF_FORBIDDEN_LOG_TERMS:
        if term in helper:
            errors.append(f"BFF log payload contains forbidden raw log input: {term}")
    if "app.log.info(" not in content or "app.log.error(" not in content:
        errors.append("BFF must emit normal and error lifecycle events")
    return errors


def validate_logging_contract(root: Path) -> list[str]:
    """Return contract violations for the backend and BFF logging surfaces."""
    try:
        return _python_contract(root) + _bff_contract(root)
    except LoggingContractError as exc:
        return [str(exc)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_logging_contract(args.root.resolve())
    if errors:
        for error in errors:
            print(f"[LOGGING-CONTRACT] {error}")
        return 1
    print("[LOGGING-CONTRACT] Structured stdout/stderr and secret-redaction contract passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
