Documentation HQ: [README](../README.md)

# Operations Readiness: Retention, Partitioning, Backup, and Restore Drills

## Scope

- Closure item: `OPS-01`, tracked in [the architecture status ledger](architecture-status.md).
- Goal: make growth-risk table management and recovery operations auditable, bounded, and repeatable without ad-hoc procedures.

## Retention and Table-Growth Control Policy

For production-like environments with PostgreSQL-backed data:

- `async_job`:
  - Retain terminal rows for `OKR_BACKEND_JOB_RETENTION_DAYS` (default: `14`).
  - Worker cleanup cadence via `OKR_BACKEND_JOB_PRUNE_INTERVAL_SECONDS` (default: `300`).
- `audit_event`:
  - Retain rows for `OKR_BACKEND_AUDIT_RETENTION_DAYS` (default: `365`).
  - Worker cleanup uses the same interval as job prune.
- Both operations must be executed in DB context and logged through existing worker observability.

Expected behavior:

- Terminal rows older than retention windows must be eligible for batch deletion.
- Deletions must be bounded by `OKR_BACKEND_JOB_PRUNE_BATCH_SIZE` to avoid long locks.
- Alerts should track retention backlog if rows fail to move.

## Partitioning Strategy for Growth-Risk Tables

Current implementation strategy (deployed-safe and migration-based):

- Keep current `async_job` and `audit_event` tables as the primary runtime tables.
- Add PostgreSQL retention/query acceleration indexes so range scans stay bounded:
  - `async_job`: status/finished_at and status/created_at index support.
  - `audit_event`: timestamp and actor/action predicate index support.
- Keep partitioning as a controlled follow-up migration once row growth exceeds index-only mitigation expectations:
  - Monthly range partitions by `created_at`.
  - Archive/read-only historical partitions after retention windows.
  - Keep an operational migration playbook for backfill and cutover.

Current gate for `OPS-01` closure:

- Verify index strategy and retention path are codified and executable by readiness checks.

## Backup and Restore Control Surface

Current production-safe controls:

- Direct DB restore endpoint exists: `POST /v1/admin/db-restore`.
- Restore path is intentionally admin-only and feature-flagged:
  - `OKR_ENABLE_DIRECT_DB_RESTORE=true` required outside hardened non-production drill mode.
  - Explicitly blocked in production runtime.
- Payload format must match `BACKUP_FORMAT_VERSION` (`okr-db-backup/v1`).
- Backend enforces 50 MB payload cap by request length for restore API.

Backup/restore commands:

- Backup export command path:
  - `GET /v1/admin/db-backup` (admin token/session required).
- Restore command path:
  - `POST /v1/admin/db-restore` (admin + `OKR_ENABLE_DIRECT_DB_RESTORE=true` + non-production runtime).

## Restore Drill Procedure (Non-Production)

This procedure must be run from an environment with controlled credentials:

1. Export current state:
   - call the backup command and store payload artifact.
2. Generate drill payload:
   - use the exported artifact; do not use external user data.
3. Dry-run restore validation:
   - load payload into a controlled staging DB via `import_database_backup`.
   - verify row counts before/after import for at least:
     - `async_job`
     - `audit_event`
4. Failure injection:
   - run a JSON version mismatch payload and verify restoration is rejected.
5. Evidence logging:
   - store command output path and timestamp in incident/logging notebook.

Completion evidence expected:

- `scripts/verify_ops01_readiness.py` passes.
- Restore drill test passes in CI or the equivalent environment using local SQLite fixture.

## Retention and Recovery Evidence Checklist

- Worker prune events emit:
  - `worker_prune_async_jobs`
  - `worker_prune_audit_events`
- Restore attempts emit `restore_attempt` audit event with payload/version metadata.
- Partition/retention SQL contract exists in migrations or approved ADR-like migration plan.
- No direct restore attempts are possible in production without controlled override policy.

