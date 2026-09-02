#!/usr/bin/env python3
"""Verify explicit repository admin/one-off process contracts.

The checks cover command surfaces and safety boundaries only. They do not claim
that a provider backup, restore, or Darkube operation has been performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _check(name: str, passed: bool, detail: str) -> dict[str, str]:
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _read(root: Path, relative: str) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except OSError:
        return ""


def build_report(root: Path = ROOT) -> dict[str, Any]:
    migration = _read(root, "scripts/verify_migration_lint.py")
    lifecycle = _read(root, "scripts/provision_saas_environment.py")
    release = _read(root, "scripts/deploy_saas_release.py")
    backup = _read(root, "scripts/backup_saas_environment.py")
    restore = _read(root, "scripts/restore_saas_environment.py")
    ci = _read(root, ".github/workflows/ci.yml")
    rollback_evidence = _read(root, "scripts/verify_rollback_evidence.py")
    recovery_evidence = _read(root, "scripts/verify_recovery_evidence.py")
    phase1_evidence = _read(root, "scripts/check_saas_phase1_evidence.py")

    checks = [
        _check(
            "migration-lint-operation",
            bool(migration)
            and all(marker in migration for marker in ("--require-baseline", "main(", "_validate_linear_chain"))
            and "uv run alembic upgrade head" in ci,
            "Migration graph validation and explicit upgrade execution are separate one-off operations.",
        ),
        _check(
            "environment-lifecycle-operation",
            bool(lifecycle)
            and all(marker in lifecycle for marker in ("provision", "suspend", "retire", "Provisioner")),
            "Environment provisioning, suspension, and retirement are explicit operator commands.",
        ),
        _check(
            "release-deploy-and-rollback-operation",
            bool(release)
            and all(marker in release for marker in ("choices=(\"deploy\", \"rollback\", \"compose-env\")", "ReleaseManager", ".rollback(")),
            "Release deployment and rollback consume explicit artifact descriptors and environment state.",
        ),
        _check(
            "backup-and-restore-boundary",
            bool(backup)
            and bool(restore)
            and all(marker in backup for marker in ("--test-only", "select_backup_provider", "BackupManager"))
            and all(marker in restore for marker in ("--isolated-target", "--test-only", "RestoreManager")),
            "Backup/restore commands require explicit provider selection and isolated restore targets.",
        ),
        _check(
            "evidence-verification-operations",
            bool(rollback_evidence)
            and bool(recovery_evidence)
            and bool(phase1_evidence)
            and all(marker in rollback_evidence for marker in ("verify_rollback_manifest", "signed Cosign references", "_verify_attestation", "synthetic"))
            and all(marker in recovery_evidence for marker in ("checksum", "isolated", "_verify_attestation", "failed evidence is not verifiable"))
            and "signature" in phase1_evidence,
            "Rollback and recovery evidence require successful, bound attestations and reject synthetic inputs.",
        ),
    ]
    return {
        "schema_version": "admin-process-contract-v1",
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
        "provider_recovery": "PENDING",
        "provider_pending": [
            "No provider-issued backup or restore evidence is asserted by this repository-only check.",
            "A real Darkube/operator rollback rehearsal remains pending until the provider is configured.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable evidence.")
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Admin process contract: {report['status']}")
        for item in report["checks"]:
            print(f"[{item['status']}] {item['name']}: {item['detail']}")
        print("[PENDING] provider_recovery: provider evidence is pending and was not fabricated.")
        for item in report["provider_pending"]:
            print(f"- {item}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
