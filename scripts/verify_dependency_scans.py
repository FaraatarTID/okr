#!/usr/bin/env python3
"""Run dependency vulnerability scans for Python and Node components."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os


ROOT = Path(__file__).resolve().parents[1]
CI_MODE = os.getenv("CI", "").lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class ScanFinding:
    scope: str
    details: str


def _run_json_command(
    command: list[str],
    *,
    cwd: Path,
    fail_on_nonzero: bool = False,
) -> tuple[int, dict[str, Any] | list[Any] | None, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, None, str(exc)

    output = completed.stdout or completed.stderr or ""
    parsed = _find_json_payload(output)
    if parsed is not None:
        return int(completed.returncode), parsed, ""
    try:
        data = json.loads(output) if output.strip() else None
        return int(completed.returncode), data, ""
    except json.JSONDecodeError:
        if fail_on_nonzero and completed.returncode != 0:
            return int(completed.returncode), None, output.strip()
        return int(completed.returncode), None, output.strip()


def _find_json_payload(output: str) -> dict[str, Any] | list[Any] | None:
    stripped = output.strip()
    if not stripped:
        return None

    candidates = [stripped]
    if stripped.find("\n") >= 0:
        candidates = [line.strip() for line in stripped.splitlines() if line.strip()]

    for candidate in reversed(candidates):
        try:
            data = json.loads(candidate)
            return data
        except json.JSONDecodeError:
            continue
    return None


def _format_finding(scope: str, package_name: str, item: Any) -> ScanFinding | None:
    if isinstance(item, str):
        return ScanFinding(scope, f"{package_name}: {item}")
    if not isinstance(item, dict):
        return None

    vuln_id = (
        item.get("id")
        or item.get("cve")
        or item.get("url")
        or item.get("name")
        or item.get("title")
        or "unknown"
    )
    severity = str(item.get("severity", "") or "unknown")
    return ScanFinding(scope, f"{package_name}: {vuln_id} ({severity})")


def _run_pip_audit() -> list[ScanFinding]:
    if shutil.which("pip-audit") is None:
        if CI_MODE:
            raise RuntimeError("pip-audit is required in CI but missing from PATH.")
        raise RuntimeError(
            "pip-audit is unavailable. Install with: python -m pip install pip-audit."
        )

    code, payload, stderr = _run_json_command(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--disable-pip",
            "--no-deps",
            "-r",
            "backend_app/requirements.txt",
            "-f",
            "json",
        ],
        cwd=ROOT,
        fail_on_nonzero=True,
    )
    if payload is None:
        if code == 0:
            return []
        raise RuntimeError(f"pip-audit failed before reporting vulnerabilities:\n{stderr}")

    vulnerabilities = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
    findings: list[ScanFinding] = []
    for vulnerability in vulnerabilities:
        if not isinstance(vulnerability, dict):
            continue
        package = str(vulnerability.get("package", "unknown"))
        ids = vulnerability.get("id") or "UNKNOWN"
        findings.append(ScanFinding("backend-python", f"{package}: {ids}"))
    return findings


def _run_npm_audit(prefix: str, *, audit_level: str = "high") -> list[ScanFinding]:
    if shutil.which("npm") is None:
        if CI_MODE:
            raise RuntimeError(f"npm is required in CI but unavailable in PATH for {prefix}.")
        raise RuntimeError("npm is unavailable in PATH.")

    code, payload, stderr = _run_json_command(
        ["npm", "audit", "--audit-level", audit_level, "--json"],
        cwd=ROOT / prefix,
        fail_on_nonzero=True,
    )
    if payload is None:
        if code == 0:
            return []
        raise RuntimeError(f"npm audit failed for {prefix}:\n{stderr}")

    vulnerabilities = payload.get("vulnerabilities", {}) if isinstance(payload, dict) else {}
    findings: list[ScanFinding] = []
    for package_name, details in vulnerabilities.items():
        if not isinstance(details, dict):
            continue

        package_findings = details.get("via") or []
        for item in package_findings:
            finding = _format_finding(prefix, package_name, item)
            if finding is None:
                continue
            severity = finding.details.rsplit("(", 1)[-1].rstrip(")").strip().lower()
            if severity in {"low", "moderate", "none", "", "unknown"}:
                continue
            findings.append(finding)

    return findings


def main() -> int:
    require_strict = CI_MODE
    findings: list[ScanFinding] = []
    had_skipped_tools = False

    try:
        findings.extend(_run_pip_audit())
    except RuntimeError as exc:
        had_skipped_tools = True
        if require_strict:
            print(f"[FAIL] Python vulnerability scanner unavailable: {exc}")
            raise
        print(f"[WARN] Python vulnerability scan skipped: {exc}")

    for prefix in ("spa-bff", "spa-web"):
        try:
            findings.extend(_run_npm_audit(prefix))
        except RuntimeError as exc:
            had_skipped_tools = True
            if require_strict:
                print(f"[FAIL] NPM audit unavailable for {prefix}: {exc}")
                raise
            print(f"[WARN] NPM audit skipped for {prefix}: {exc}")

    if not findings:
        if had_skipped_tools:
            print("Dependency vulnerability scan completed with warnings (some scanners unavailable).")
            return 0
        print("Dependency vulnerability scan completed with no findings.")
        return 0

    print("Dependency vulnerability scan found issues that require remediation:")
    for finding in findings:
        print(f"- {finding.scope}: {finding.details}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
