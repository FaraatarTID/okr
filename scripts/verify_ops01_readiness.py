#!/usr/bin/env python3
"""Verify OPS-01 operational maturity closure artifacts and contracts."""

from __future__ import annotations

from pathlib import Path


def _validate_file(path: Path, required_strings: list[str], label: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append(f"Missing {label}: {path.as_posix()}")
        return errors

    content = path.read_text(encoding="utf-8")
    for needle in required_strings:
        if needle not in content:
            errors.append(f"{label}: missing required phrase '{needle}'")
    return errors


def main() -> int:
    errors: list[str] = []

    required_files = [
        ("docs/OPS_READINESS_AND_RECOVERY_GUIDE.md", [
            "Retention and Table-Growth Control Policy",
            "Partitioning Strategy for Growth-Risk Tables",
            "Backup and Restore Control Surface",
            "Restore Drill Procedure",
        ]),
        ("src/database.py", [
            "export_database_backup()",
            "import_database_backup",
            "BACKUP_FORMAT_VERSION",
        ]),
        ("backend_app/jobs.py", [
            "def prune_terminal_jobs",
            "def prune_audit_events",
        ]),
        ("backend_app/worker.py", [
            "worker_prune_async_jobs",
            "worker_prune_audit_events",
        ]),
        ("backend_app/config.py", [
            "OKR_BACKEND_JOB_RETENTION_DAYS",
            "OKR_BACKEND_AUDIT_RETENTION_DAYS",
            "OKR_BACKEND_JOB_PRUNE_INTERVAL_SECONDS",
            "OKR_BACKEND_JOB_PRUNE_BATCH_SIZE",
        ]),
        ("backend_app/routers/platform_routes.py", [
            "/v1/admin/db-backup",
            "/v1/admin/db-restore",
            "OKR_ENABLE_DIRECT_DB_RESTORE",
        ]),
    ]

    for rel, markers in required_files:
        errors.extend(
            _validate_file(Path(rel), markers, rel.replace("\\", "/"))
        )

    migration = Path("alembic/versions/bc1d2e3f4a5b_ops01_growth_table_indexes.py")
    if migration.exists():
        # Legacy per-migration artifact (pre-baseline-squash). If present,
        # verify its contract markers.
        migration_checks = [
            "bc1d2e3f4a5b",
            "async_job",
            "audit_event",
            "create_index",
        ]
        errors.extend(
            _validate_file(migration, migration_checks, migration.as_posix())
        )
    else:
        # Post-squash: the growth indexes live in the baseline schema. Verify
        # the baseline exists and carries the index contract instead.
        baseline = Path("alembic/versions/baseline_2026_08_26_schema.py")
        if not baseline.exists():
            errors.append(
                "Missing OPS-01 growth-index source: neither the legacy "
                "migration nor the baseline schema was found."
            )
        else:
            errors.extend(
                _validate_file(
                    baseline,
                    ["ix_async_job_status_created", "ix_audit_event_actor_created"],
                    baseline.as_posix(),
                )
            )

    if errors:
        for issue in errors:
            print(f"OPS-01 CHECK FAILED: {issue}")
        return 1

    print("OPS-01 readiness verification passed.")
    print(
        "Contracts checked: retention policy, growth indexes contract, backup/restore path."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
