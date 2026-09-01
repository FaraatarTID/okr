#!/usr/bin/env python3
"""Verify a remote, disposable pre-release deployment.

This verifier checks HTTP endpoints and separately labels operator-supplied
evidence. It does not infer targets from environment variables and never prints
response bodies, URLs, or exception text.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_EVIDENCE_LENGTH = 64 * 1024
SMOKE_SCOPES = ("full", "public", "private")
HEALTHY_WORKER_STATUSES = {"ok", "healthy", "ready", "running", "succeeded"}
_SENSITIVE_MARKER_RE = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|private[_-]?key)\s*[:=]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SmokeCheck:
    """The sanitized outcome of one pre-release check."""

    name: str
    ok: bool
    detail: str
    status_code: int | None = None
    evidence_type: str = "INDEPENDENT"

    @property
    def passed(self) -> bool:
        """Compatibility alias for callers that use pass/fail terminology."""
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreReleaseSmokeResult:
    """Complete, JSON-serializable result for a pre-release smoke run."""

    checks: tuple[SmokeCheck, ...]
    duration_seconds: float
    started_at: str

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def passed(self) -> bool:
        return self.ok

    @property
    def independent_ok(self) -> bool:
        """Whether every independently executed check passed."""
        independent_checks = [
            check for check in self.checks if check.evidence_type == "INDEPENDENT"
        ]
        return bool(independent_checks) and all(check.ok for check in independent_checks)

    @property
    def summary(self) -> str:
        passed = sum(check.ok for check in self.checks)
        return f"{passed}/{len(self.checks)} pre-release smoke checks passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "independent_ok": self.independent_ok,
            "summary": self.summary,
            "started_at": self.started_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "checks": [check.to_dict() for check in self.checks],
        }


def _validate_timeout(timeout_seconds: float) -> float:
    timeout = float(timeout_seconds)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be a finite positive number")
    if timeout > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must not exceed {MAX_TIMEOUT_SECONDS:g}")
    return timeout


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must use http or https and include a host")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not accepted")


def _safe_http_error(url: str, timeout_seconds: float) -> tuple[bool, int | None, str, bytes]:
    """Fetch one URL while keeping all diagnostics independent of remote data."""
    try:
        _validate_url(url)
    except ValueError:
        return False, None, "invalid endpoint URL", b""

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json, text/html;q=0.9"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 0) or 0)
            body = response.read(MAX_EVIDENCE_LENGTH + 1)
    except urllib.error.HTTPError as exc:
        return False, int(exc.code), f"HTTP {int(exc.code)}", b""
    except (TimeoutError, urllib.error.URLError):
        return False, None, "request timed out or endpoint was unreachable", b""
    except OSError:
        return False, None, "request failed", b""

    if status_code < 200 or status_code >= 300:
        return False, status_code, f"HTTP {status_code}", b""
    if len(body) > MAX_EVIDENCE_LENGTH:
        return False, status_code, "response exceeded the diagnostic size limit", b""
    return True, status_code, f"HTTP {status_code}", body


def _http_check(name: str, url: str, timeout_seconds: float, *, health_json: bool) -> SmokeCheck:
    ok, status_code, detail, body = _safe_http_error(url, timeout_seconds)
    if not ok:
        return SmokeCheck(name=name, ok=False, detail=detail, status_code=status_code)

    if not health_json:
        return SmokeCheck(name=name, ok=True, detail=f"{detail}; endpoint reachable", status_code=status_code)

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return SmokeCheck(
            name=name,
            ok=False,
            detail="health endpoint returned invalid JSON",
            status_code=status_code,
        )
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return SmokeCheck(
            name=name,
            ok=False,
            detail="health endpoint did not report status=ok",
            status_code=status_code,
        )
    return SmokeCheck(name=name, ok=True, detail=f"{detail}; status=ok", status_code=status_code)


def _contains_sensitive_marker(value: str) -> bool:
    return bool(_SENSITIVE_MARKER_RE.search(value)) or "postgresql://" in value.lower()


def _worker_status(evidence: str | Mapping[str, Any] | None) -> str | None:
    if evidence is None:
        return None
    if isinstance(evidence, Mapping):
        value = evidence.get("status")
        return str(value).strip().lower() if value is not None else None
    text = evidence.strip()
    if not text or _contains_sensitive_marker(text) or len(text) > MAX_EVIDENCE_LENGTH:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        value = parsed.get("status")
        return str(value).strip().lower() if value is not None else None
    match = re.search(r"\bstatus\s*[:=]\s*([a-zA-Z]+)\b", text, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    if text.lower() in HEALTHY_WORKER_STATUSES:
        return text.lower()
    return None


def _worker_check(evidence: str | Mapping[str, Any] | None) -> SmokeCheck:
    if evidence is None:
        return SmokeCheck(
            "worker", False, "worker evidence was not supplied", evidence_type="MANUAL_ATTESTATION"
        )
    status = _worker_status(evidence)
    if status is None:
        return SmokeCheck(
            "worker",
            False,
            "worker evidence was missing, invalid, or unsanitized",
            evidence_type="MANUAL_ATTESTATION",
        )
    if status not in HEALTHY_WORKER_STATUSES:
        return SmokeCheck(
            "worker",
            False,
            "worker evidence did not report a healthy status",
            evidence_type="MANUAL_ATTESTATION",
        )
    return SmokeCheck(
        "worker",
        True,
        "sanitized worker evidence reports a healthy status",
        evidence_type="MANUAL_ATTESTATION",
    )


def _migration_check(migration_head: str | None, expected_migration_head: str | None) -> SmokeCheck:
    if migration_head is None or not migration_head.strip():
        return SmokeCheck(
            "migration",
            False,
            "migration head evidence was not supplied",
            evidence_type="MANUAL_ATTESTATION",
        )
    head = migration_head.strip()
    if len(head) > 256 or any(char.isspace() for char in head) or _contains_sensitive_marker(head):
        return SmokeCheck(
            "migration",
            False,
            "migration head evidence was invalid or unsanitized",
            evidence_type="MANUAL_ATTESTATION",
        )
    if expected_migration_head is not None and head != expected_migration_head.strip():
        return SmokeCheck(
            "migration",
            False,
            "migration head did not match the expected head",
            evidence_type="MANUAL_ATTESTATION",
        )
    return SmokeCheck(
        "migration",
        True,
        "sanitized migration head evidence was supplied",
        evidence_type="MANUAL_ATTESTATION",
    )


def verify_prerelease_smoke(
    *,
    web_url: str | None = None,
    bff_health_url: str | None = None,
    api_health_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    worker_evidence: str | Mapping[str, Any] | None = None,
    migration_head: str | None = None,
    expected_migration_head: str | None = None,
    scope: str = "full",
) -> PreReleaseSmokeResult:
    """Run public, private, or complete remote checks without crossing boundaries."""
    if scope not in SMOKE_SCOPES:
        raise ValueError(f"scope must be one of: {', '.join(SMOKE_SCOPES)}")
    timeout = _validate_timeout(timeout_seconds)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    checks: list[SmokeCheck] = []
    if scope in {"full", "public"}:
        if not web_url or not bff_health_url:
            raise ValueError("public scope requires web_url and bff_health_url")
        checks.extend(
            (
                _http_check("web", web_url, timeout, health_json=False),
                _http_check("bff", bff_health_url, timeout, health_json=True),
            )
        )
    if scope in {"full", "private"}:
        if not api_health_url:
            raise ValueError("private scope requires api_health_url")
        checks.extend(
            (
                _http_check("api", api_health_url, timeout, health_json=True),
                _worker_check(worker_evidence),
                _migration_check(migration_head, expected_migration_head),
            )
        )
    return PreReleaseSmokeResult(
        checks=tuple(checks),
        duration_seconds=max(0.0, time.monotonic() - started),
        started_at=started_at,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a remote Darkube pre-release deployment.")
    parser.add_argument("--scope", choices=SMOKE_SCOPES, default="full")
    parser.add_argument("--web-url", help="Public pre-release web URL.")
    parser.add_argument("--bff-health-url", help="Public pre-release BFF health URL.")
    parser.add_argument("--api-health-url", help="Private pre-release API health URL.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--worker-evidence", help="Sanitized worker status, for example status=running.")
    parser.add_argument("--worker-evidence-file", type=Path, help="File containing sanitized worker evidence.")
    parser.add_argument("--migration-head", help="Sanitized migration head observed in the deployment.")
    parser.add_argument("--expected-migration-head", help="Expected migration head to compare against.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if args.worker_evidence is not None and args.worker_evidence_file is not None:
        parser.error("use only one of --worker-evidence and --worker-evidence-file")
    if args.worker_evidence_file is not None:
        try:
            args.worker_evidence = args.worker_evidence_file.read_text(encoding="utf-8")
        except OSError:
            parser.error("unable to read --worker-evidence-file")
    if args.scope in {"full", "public"} and (not args.web_url or not args.bff_health_url):
        parser.error("the selected scope requires --web-url and --bff-health-url")
    if args.scope in {"full", "private"} and not args.api_health_url:
        parser.error("the selected scope requires --api-health-url")
    return args


def _print_text(result: PreReleaseSmokeResult) -> None:
    for check in result.checks:
        flag = check.evidence_type if check.evidence_type != "INDEPENDENT" else ("PASS" if check.ok else "FAIL")
        print(f"[{flag}] {check.name}: {check.detail}")
    print(
        f"{result.summary}; independent_ok={result.independent_ok}; "
        f"duration={result.duration_seconds:.3f}s"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = verify_prerelease_smoke(
            scope=args.scope,
            web_url=args.web_url,
            bff_health_url=args.bff_health_url,
            api_health_url=args.api_health_url,
            timeout_seconds=args.timeout_seconds,
            worker_evidence=args.worker_evidence,
            migration_head=args.migration_head,
            expected_migration_head=args.expected_migration_head,
        )
    except ValueError as exc:
        if args.format == "json":
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"[FAIL] configuration: {exc}")
        return 2
    if args.format == "json":
        print(json.dumps(result.to_dict(), sort_keys=True))
    else:
        _print_text(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
