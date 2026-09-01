# Hamravesh Production Backup and Restore Onboarding

Documentation HQ: [README](../../README.md)

**Status:** provider selection and the first production-shaped restore
rehearsal are pending. This document does not authorize customer-data
onboarding.

Hamravesh advertises automatic, off-site backup storage, configurable backup
intervals and retention versions, backup inspection, and backup-health checks.
Confirm the exact database product behavior in the Hamravesh console before
treating those capabilities as PostgreSQL recovery evidence.

## 1. Provider confirmation gate

The operations owner must record `PASS`, `FAIL`, or `NOT AVAILABLE` for each
item below, with a console reference or provider support confirmation:

- The selected managed PostgreSQL service is identified by an opaque provider resource ID.
- Backups cover database contents needed to restore the application, not only application disks.
- Schedule, retention, encryption, and off-site location are configurable and recorded.
- Restore can target a separate database without overwriting the source.
- The provider exposes backup ID, restore ID, source/target identity, status, checksum or integrity result, and timestamps.
- The target can remain private and isolated from production traffic.
- Backup and restore failure alerts are available to the operations owner.
- Retention and deletion behavior meet the agreed RPO/RTO and contract requirements.

If any required item is `FAIL` or `NOT AVAILABLE`, stop provider integration.
Do not substitute a disk snapshot, local adapter, or public database for a
logical database restore without an explicit architecture decision.

## 2. Configure the rehearsal environment

Use a non-customer rehearsal environment first. Store credentials in the
Hamravesh console or approved secret manager, never in GitHub or evidence.

Record only sanitized metadata:

- Environment ID
- Opaque database resource ID
- Backup policy ID and backup ID
- Restore target resource ID
- Operations owner
- RPO and RTO targets

Do not record connection URLs, passwords, access keys, tokens, or database
contents in the evidence bundle.

## 3. Execute the restore rehearsal

1. Confirm the source database is the intended non-production environment.
2. Trigger or wait for a completed provider backup.
3. Verify the backup status and provider-issued integrity/checksum result.
4. Create a separate restore target with production access disabled.
5. Restore the backup into that target through the Hamravesh console.
6. Record the provider restore ID and start/completion timestamps.
7. Verify the restored schema, migration revision, expected synthetic fixtures, and application health without public exposure.
8. Measure RPO and RTO from provider and operator timestamps.
9. Run `scripts/verify_recovery_evidence.py` against sanitized evidence.
10. Delete the temporary restore target only after preserving the evidence.

The restore target must never be the live customer database. This rehearsal is
separate from application image rollback and does not validate migration
downgrades.

## 4. Evidence contract

Create a sanitized JSON file with this shape. Values shown are examples, not
usable credentials or provider identifiers:

```json
{
  "schema_version": 1,
  "environment_id": "customer-a-prod",
  "database": {
    "identity": "hamravesh-db-resource-redacted",
    "provider": "hamravesh",
    "environment_id": "customer-a-prod"
  },
  "backup": {
    "id": "backup-redacted",
    "status": "SUCCESS",
    "checksum": "sha256:<64-hex-digest>",
    "verified_at": "2026-09-01T12:00:00Z"
  },
  "restore": {
    "status": "SUCCESS",
    "started_at": "2026-09-01T12:01:00Z",
    "completed_at": "2026-09-01T12:21:00Z",
    "restored_checksum": "sha256:<64-hex-digest>",
    "target": {
      "identity": "hamravesh-restore-resource-redacted",
      "environment_id": "customer-a-prod",
      "isolation": "isolated",
      "live": false
    }
  },
  "rpo_target_seconds": 3600,
  "rto_target_seconds": 1800,
  "measured_rpo_seconds": 900,
  "measured_rto_seconds": 1200,
  "status": "PASSED",
  "operator": "operations-owner"
}
```

Run:

```bash
python scripts/verify_recovery_evidence.py \
  --evidence hamravesh-recovery-evidence.json \
  --output hamravesh-recovery-verification.json
```

The verification file validates the recorded contract only. It does not claim
that Hamravesh performed the operation unless provider IDs, statuses, and
timestamps have been independently retained by the operator.

## 5. Production entry decision

Production customer-data onboarding remains blocked until all of the following
are present:

- Provider confirmation gate completed.
- Successful provider backup.
- Successful isolated restore with matching checksum.
- Measured RPO and RTO within target.
- Named operations owner and customer-environment operator.
- Application rollback evidence for the same release boundary.
- Explicit real-data approval.

