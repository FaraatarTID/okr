#!/usr/bin/env python3
"""Verify dependency license policy for Python and Node dependencies."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CI_MODE = os.getenv("CI", "").lower() in {"1", "true", "yes"}
POLICY_PATH = Path(__file__).with_name("dependency_license_policy.json")


@dataclass(frozen=True)
class LicenseFinding:
    scope: str
    package: str
    license_name: str
    detail: str


@dataclass(frozen=True)
class ScopeLicensePolicy:
    allowed_licenses: tuple[str, ...]
    package_exceptions: dict[str, tuple[str, ...]]


def _read_policy() -> tuple[dict[str, str], dict[str, ScopeLicensePolicy]]:
    if not POLICY_PATH.exists():
        raise RuntimeError(f"Dependency license policy file missing: {POLICY_PATH.relative_to(ROOT)}")

    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    raw_scopes = payload.get("scopes")
    if not isinstance(raw_scopes, dict):
        raise RuntimeError("Policy file must define a 'scopes' mapping.")

    raw_aliases = payload.get("license_aliases", {})
    aliases = {
        str(alias).strip().lower(): str(canonical).strip()
        for alias, canonical in raw_aliases.items()
        if isinstance(alias, str) and isinstance(canonical, str)
    }

    policies: dict[str, ScopeLicensePolicy] = {}
    for scope, raw in raw_scopes.items():
        if not isinstance(scope, str):
            continue
        if not isinstance(raw, dict):
            continue

        allowed = tuple(
            str(item).strip()
            for item in raw.get("allowed_licenses", [])
            if isinstance(item, str) and item.strip()
        )
        raw_exceptions = raw.get("package_exceptions", {})
        package_exceptions: dict[str, tuple[str, ...]] = {}
        if isinstance(raw_exceptions, dict):
            for package, allowed_list in raw_exceptions.items():
                if not isinstance(package, str):
                    continue
                package_key = package.lower().strip()
                if isinstance(allowed_list, str):
                    package_exceptions[package_key] = (allowed_list.strip(),)
                elif isinstance(allowed_list, list):
                    package_exceptions[package_key] = tuple(
                        str(item).strip()
                        for item in allowed_list
                        if isinstance(item, str) and item.strip()
                    )

        if not allowed:
            raise RuntimeError(f"Scope '{scope}' has no allowed_licenses configured.")

        policies[scope] = ScopeLicensePolicy(
            allowed_licenses=tuple(_normalize_license_expression(item, aliases) for item in allowed),
            package_exceptions=package_exceptions,
        )

    if not policies:
        raise RuntimeError("Policy file did not produce any active scope configuration.")

    return aliases, policies


def _normalize_license_expression(expr: str, aliases: dict[str, str] | None = None) -> str:
    aliases = aliases or {}
    normalized = re.sub(r"\s+", " ", str(expr).strip()).strip(" .\"'")
    normalized = normalized.replace("Version ", "")
    if normalized.startswith("SEE LICENSE"):
        return normalized
    lower = normalized.lower()
    if lower in aliases:
        return aliases[lower]
    if lower in {"mpl", "mpl 2", "mpl 2.0", "mozilla public license 2.0"}:
        return "MPL-2.0"
    if lower in {"python software foundation license", "python software foundation"}:
        return "Python Software Foundation License"
    if lower in {"psf", "psf-2"}:
        return "PSF-2.0"
    return normalized


def _split_license_terms(license_name: str) -> Iterable[str]:
    terms: list[str]
    if " OR " in license_name:
        terms = license_name.split(" OR ")
    elif " AND " in license_name:
        terms = license_name.split(" AND ")
    elif ";" in license_name:
        terms = license_name.split(";")
    else:
        terms = [license_name]

    for term in terms:
        normalized = _normalize_license_expression(term)
        if normalized:
            yield normalized


def _is_allowed_license_expr(license_name: str, policy: ScopeLicensePolicy, aliases: dict[str, str]) -> bool:
    normalized = _normalize_license_expression(license_name, aliases)
    if normalized in {"", "unknown"}:
        return False
    if normalized == "SEE LICENSE":
        return False
    if normalized in policy.allowed_licenses:
        return True
    terms = tuple(_split_license_terms(normalized))
    return all(term in policy.allowed_licenses for term in terms)


def _run_pip_licenses(policy: ScopeLicensePolicy, aliases: dict[str, str]) -> list[LicenseFinding]:
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
        package_key = package.lower()
        license_name = _normalize_license_expression(str(row.get("License", "unknown")), aliases)
        if not license_name or license_name == "unknown":
            continue

        package_allowed = package_key in policy.package_exceptions and (
            _is_allowed_license_expr(license_name, ScopeLicensePolicy(policy.allowed_licenses, {}), aliases)
            or any(_normalize_license_expression(item, aliases) == license_name for item in policy.package_exceptions[package_key])
        )
        if package_allowed:
            continue

        if not _is_allowed_license_expr(license_name, policy, aliases):
            findings.append(
                LicenseFinding(
                    scope="backend-python",
                    package=package,
                    license_name=license_name,
                    detail="not in allowed license policy",
                )
            )

    return findings


def _run_npm_lock_scan(prefix: str, policy: ScopeLicensePolicy, aliases: dict[str, str]) -> list[LicenseFinding]:
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
        license_name = _normalize_license_expression(str(meta.get("license", "unknown")), aliases)
        if not license_name or license_name == "unknown":
            continue
        package_name = name.removeprefix("node_modules/") if name.startswith("node_modules/") else name
        package_key = package_name.lower()

        package_allowed = package_key in policy.package_exceptions and any(
            _normalize_license_expression(item, aliases) == license_name
            for item in policy.package_exceptions[package_key]
        )
        if package_allowed:
            continue
        if _is_allowed_license_expr(license_name, policy, aliases):
            continue

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
    aliases, policies = _read_policy()

    findings: list[LicenseFinding] = []
    unavailable = False

    try:
        findings.extend(_run_pip_licenses(policies["backend-python"], aliases))
    except RuntimeError as exc:
        unavailable = True
        if CI_MODE:
            raise RuntimeError(f"Python license scan unavailable in CI: {exc}")
        print(f"[WARN] Python license scan skipped: {exc}")

    for prefix in ("spa-bff", "spa-web"):
        try:
            policy = policies[prefix]
            findings.extend(_run_npm_lock_scan(prefix, policy, aliases))
        except KeyError as exc:
            raise RuntimeError(f"No policy defined for scope: {exc}") from exc
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
