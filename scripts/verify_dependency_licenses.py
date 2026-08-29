#!/usr/bin/env python3
"""Verify dependency license policy for Python and Node dependencies."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_MODE = os.getenv("CI", "").lower() in {"1", "true", "yes"}

ALLOWED_LICENSES = {
    "0BSD",
    "Apache-2.0",
    "Apache Software License",
    "Apache Software License; MIT License",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BSD-3-Clause-Clear",
    "BSD License",
    "CC0-1.0",
    "GNU Library or Lesser General Public License (LGPL)",
    "ISC",
    "LGPL",
    "MIT",
    "MIT License",
    "MIT-0",
    "MPL-2.0",
    "Python-2.0",
    "Python Software Foundation License",
    "PSF",
    "PSF-2.0",
    "Unlicense",
}

LICENSE_EXCEPTIONS = {
    "spa-web": {
        "caniuse-lite": {"CC-BY-4.0", "no-restriction"},
        "@img/sharp-wasm32": {"Apache-2.0 AND LGPL-3.0-or-later AND MIT": "license-combo-known"},
        "@img/sharp-win32-arm64": {"Apache-2.0 AND LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-win32-ia32": {"Apache-2.0 AND LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-win32-x64": {"Apache-2.0 AND LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-darwin-arm64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-darwin-x64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linux-arm": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linux-arm64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linux-ppc64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linux-riscv64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linux-s390x": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linux-x64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linuxmusl-arm64": {"LGPL-3.0-or-later": "license-combo-known"},
        "@img/sharp-libvips-linuxmusl-x64": {"LGPL-3.0-or-later": "license-combo-known"},
    }
}


def _is_allowed_license_expr(license_name: str) -> bool:
    if license_name in ALLOWED_LICENSES:
        return True
    # SPDX-style expressions can wrap the whole expression in parentheses
    # (e.g. "(MIT OR CC0-1.0)"). Strip outer parentheses before splitting so
    # each branch is matched against ALLOWED_LICENSES.
    expr = license_name.strip()
    while expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1].strip()
    if " OR " in expr:
        return all(part.strip() in ALLOWED_LICENSES for part in expr.split(" OR "))
    if " AND " in expr:
        return all(part.strip() in ALLOWED_LICENSES for part in expr.split(" AND "))
    if ";" in expr:
        return all(part.strip() in ALLOWED_LICENSES for part in expr.split(";"))
    return False


@dataclass(frozen=True)
class LicenseFinding:
    scope: str
    package: str
    license_name: str
    detail: str


def _normalize_license(value: str) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip()
    if normalized in {"Mozilla Public License 2.0 (MPL 2.0)", "Mozilla Public License Version 2.0"}:
        return "MPL-2.0"
    if normalized.startswith("Mozilla Public License") and "MPL 2.0" in normalized:
        return "MPL-2.0"
    if "/" in normalized and normalized.upper().startswith("SEE LICENSE"):
        return "SEE LICENSE"
    return normalized


def _run_pip_licenses() -> list[LicenseFinding]:
    if not shutil.which("pip-licenses"):
        raise RuntimeError("pip-licenses is unavailable. Install with: python -m pip install pip-licenses.")

    completed = subprocess.run(
        [
            "pip-licenses",
            "--format=json",
            "--from=mixed",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"pip-licenses failed: {completed.stderr or completed.stdout}")

    try:
        rows = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pip-licenses returned non-JSON output: {exc}") from exc

    findings: list[LicenseFinding] = []
    for row in rows:
        package = str(row.get("Name", "unknown"))
        license_name = _normalize_license(str(row.get("License", "unknown")))
        if not _is_allowed_license_expr(license_name):
            findings.append(
                LicenseFinding(
                    scope="backend-python",
                    package=package,
                    license_name=license_name,
                    detail="not in allowed license policy",
                )
            )
    return findings


def _run_npm_lock_scan(prefix: str) -> list[LicenseFinding]:
    lock_path = ROOT / prefix / "package-lock.json"
    if not lock_path.exists():
        raise RuntimeError(f"Missing lockfile: {lock_path.relative_to(ROOT)}")

    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    packages = payload.get("packages")
    if not isinstance(packages, dict):
        raise RuntimeError(f"Unexpected package-lock format for {prefix}")

    findings: list[LicenseFinding] = []
    for name, meta in packages.items():
        if not isinstance(meta, dict) or name == "":
            continue
        license_name = _normalize_license(str(meta.get("license", "unknown")))
        if license_name == "unknown":
            continue
        package_name = name.removeprefix("node_modules/") if name.startswith("node_modules/") else name
        allowed_for_package = LICENSE_EXCEPTIONS.get(prefix, {}).get(package_name)
        if (
            (license_name not in ALLOWED_LICENSES)
            and (not _is_allowed_license_expr(license_name))
            and not allowed_for_package
        ):
            package_name = name.removeprefix("node_modules/") if name.startswith("node_modules/") else name
            findings.append(
                LicenseFinding(
                    scope=prefix,
                    package=package_name,
                    license_name=license_name,
                    detail="not in allowed license policy",
                )
            )
    return findings


def _summarize(findings: list[LicenseFinding]) -> None:
    if not findings:
        print("Dependency license checks completed with no violations.")
        return

    print("Dependency license policy violations detected:")
    for finding in findings:
        print(
            "- "
            f"{finding.scope}: {finding.package} ({finding.license_name}) "
            f"{finding.detail}"
        )


def main() -> int:
    findings: list[LicenseFinding] = []
    unavailable = False

    try:
        findings.extend(_run_pip_licenses())
    except RuntimeError as exc:
        unavailable = True
        if CI_MODE:
            raise RuntimeError(f"Python license scan unavailable in CI: {exc}")
        print(f"[WARN] Python license scan skipped: {exc}")

    for prefix in ("spa-bff", "spa-web"):
        try:
            findings.extend(_run_npm_lock_scan(prefix))
        except RuntimeError as exc:
            unavailable = True
            if CI_MODE:
                raise RuntimeError(f"Node license scan unavailable in CI for {prefix}: {exc}")
            print(f"[WARN] Node license scan skipped for {prefix}: {exc}")

    _summarize(findings)

    if findings:
        return 1

    if unavailable:
        print("Dependency license checks completed with warnings (some scans unavailable).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
