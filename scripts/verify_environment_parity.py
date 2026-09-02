#!/usr/bin/env python3
"""Verify repository-defined CI, staging, production, and local parity.

This is deliberately provider-independent. It proves the contracts represented
in repository files and reports live Darkube evidence as pending rather than
inferring it from configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.verify_darkube_deployment import DeploymentVerificationError, verify_deployment
except ModuleNotFoundError:  # Direct invocation: python scripts/verify_environment_parity.py
    from verify_darkube_deployment import DeploymentVerificationError, verify_deployment


ROOT = Path(__file__).resolve().parents[1]


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _read(root: Path, relative: str) -> str:
    path = root / relative
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_report(
    root: Path = ROOT,
    *,
    manifest_path: Path | None = None,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    ci = _read(root, ".github/workflows/ci.yml")
    staging = _read(root, ".github/workflows/darkube-prerelease.yml")
    production = _read(root, ".github/workflows/promote-production.yml")
    compose = _read(root, "deploy/docker/docker-compose.yml")
    darkube_verifier = _read(root, "scripts/verify_darkube_deployment.py")

    checks = [
        _check(
            "ci-build-test-contract",
            bool(ci)
            and all(
                marker in ci
                for marker in (
                    "uv sync --locked",
                    "python -m pytest",
                    "npm ci",
                    "npm run typecheck --workspace spa-web",
                    "npm run build --workspace spa-web",
                )
            ),
            "CI defines locked dependency, Python test, JavaScript install, SPA typecheck, and SPA build steps.",
        ),
        _check(
            "staging-immutable-image-contract",
            bool(staging)
            and all(
                marker in staging
                for marker in (
                    "RELEASE_SHA",
                    "ghcr.io/${GITHUB_REPOSITORY,,}",
                    "docker push",
                    "darkube_deployment_evidence_json",
                )
            ),
            "Staging publishes commit-SHA GHCR images and accepts sanitized provider evidence.",
        ),
        _check(
            "production-promotion-contract",
            bool(production)
            and all(
                marker in production
                for marker in (
                    "staging_run_id",
                    "release_sha",
                    "production-promotion.json",
                    "environment: production",
                    "digest",
                )
            ),
            "Production promotion requires staging evidence, protected approval, and digest-pinned release data.",
        ),
        _check(
            "local-compose-topology",
            bool(compose)
            and all(
                f"  {service}:" in compose
                for service in (
                    "postgres",
                    "backend-api",
                    "backend-worker",
                    "spa-bff",
                    "spa-web",
                )
            )
            and "restart: unless-stopped" in compose
            and "healthcheck:" in compose,
            "Local Compose defines the database, API, worker, BFF, and web processes with health/restart policy.",
        ),
        _check(
            "provider-evidence-verifier",
            bool(darkube_verifier)
            and all(marker in darkube_verifier for marker in ("sha256:[0-9a-f]{64}", "applications", "manifest")),
            "Darkube evidence is accepted only through exact manifest and digest verification.",
        ),
    ]
    provider_evidence = "PENDING_PROVIDER_EVIDENCE"
    provider_evidence_reason = "evidence_not_supplied"
    provider_error = None
    if manifest_path is not None or evidence_path is not None:
        if manifest_path is None or evidence_path is None:
            provider_evidence = "FAIL"
            provider_evidence_reason = "manifest_and_evidence_required_together"
            provider_error = "manifest and evidence must be supplied together"
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                verify_deployment(manifest, evidence)
            except (DeploymentVerificationError, OSError, json.JSONDecodeError) as exc:
                provider_evidence = "FAIL"
                provider_evidence_reason = "evidence_not_verifiable"
                provider_error = str(exc)
            else:
                provider_evidence = "PASS"
                provider_evidence_reason = "sanitized_evidence_verified"

    report = {
        "schema_version": "environment-parity-v1",
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) and provider_evidence != "FAIL" else "FAIL",
        "repository_contract": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
        "provider_evidence": provider_evidence,
        "provider_evidence_reason": provider_evidence_reason,
        "provider_pending": [
            "Darkube staging/production deployment and ingress have not been observed by this provider-independent check.",
            "Provider restart behavior and live staging-to-production parity remain pending.",
        ],
    }
    if provider_error:
        report["provider_evidence_error"] = provider_error
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable evidence.")
    parser.add_argument("--manifest", type=Path, help="Release manifest paired with sanitized provider evidence.")
    parser.add_argument("--evidence", type=Path, help="Sanitized Darkube deployment evidence JSON.")
    args = parser.parse_args(argv)
    report = build_report(manifest_path=args.manifest, evidence_path=args.evidence)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Repository parity contract: {report['repository_contract']}")
        for item in report["checks"]:
            print(f"[{item['status']}] {item['name']}: {item['detail']}")
        print(f"[{report['provider_evidence']}] provider_evidence: {report['provider_evidence_reason']}")
        if report.get("provider_evidence_error"):
            print(f"- {report['provider_evidence_error']}")
        for item in report["provider_pending"]:
            print(f"- {item}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
