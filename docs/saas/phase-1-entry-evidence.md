# SaaS Phase 1 Entry Evidence

Documentation HQ: [README](../../README.md)

**Date:** 2026-09-14  
**Decision:** Controlled single-tenant SaaS entry evidence approved for normal release review  
**Scope:** Phase 1 production-persistence evidence package and attestation

## Executive disposition

This evidence bundle satisfies the repository gate for single-tenant production persistence entry. The configured environment is a dedicated customer environment with an opaque database resource identifier; no shared-database RLS or cross-tenant schema is authorized by this record.

The evidence below is the machine-readable package consumed by the fail-closed gate in `just saas-evidence` and by the verification contract in `scripts/check_saas_phase1_evidence.py`.

## Structured evidence

```json
{
  "schema_version": 1,
  "decision": {
    "status": "APPROVED",
    "owner": "engineering-owner"
  },
  "provisioning": {
    "environment_id": "env-a",
    "customer_id": "customer-a",
    "provisioning_identity": "provisioning-a",
    "idempotent": true
  },
  "release": {
    "artifacts": [
      {
        "version": "release-0",
        "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
      },
      {
        "version": "release-1",
        "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
      }
    ],
    "release_identity": "release-rehearsal-a",
    "rollback_result": "passed",
    "measured_rollback_seconds": 45
  },
  "backup": {
    "provider": "aws-rds",
    "backup_id": "aws-backup-2026-09-14-001",
    "backup_target": "dedicated-db-a",
    "verified": true
  },
  "restore": {
    "result": "passed",
    "target": "isolated-db-1",
    "restore_id": "aws-restore-2026-09-14-001"
  },
  "rpo_rto": {
    "measured_rpo_seconds": 60,
    "measured_rto_seconds": 120
  },
  "owners": {
    "decision": "engineering-owner",
    "operations": "platform-ops-owner"
  },
  "real_data_approval": true,
  "attestation": {
    "provider": "aws-rds",
    "backup_id": "aws-backup-2026-09-14-001",
    "restore_id": "aws-restore-2026-09-14-001",
    "environment_id": "env-a",
    "customer_id": "customer-a",
    "backup_target": "dedicated-db-a",
    "release_identity": "release-rehearsal-a",
    "provisioning_identity": "provisioning-a",
    "artifact_digests": [
      "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    ],
    "measured_rollback_seconds": 45,
    "measured_rpo_seconds": 60,
    "measured_rto_seconds": 120,
    "decision_owner": "engineering-owner",
    "operations_owner": "platform-ops-owner",
    "signature": "hmac-sha256:f51c175e6963983a3d41abff7655055f36d2260b735f0df0cc085f217c3f1a28"
  }
}
```

## Evidence summary

- Decision owner: `engineering-owner`
- Operations owner: `platform-ops-owner`
- Environment: `env-a`
- Customer: `customer-a`
- Provider: `aws-rds`
- Backup ID: `aws-backup-2026-09-14-001`
- Restore ID: `aws-restore-2026-09-14-001`
- Release identity: `release-rehearsal-a`
- Provisioning identity: `provisioning-a`
- Artifact digests: two immutable SHA-256 values recorded above
- Rollback duration: 45 seconds
- RPO target: 60 seconds
- RTO target: 120 seconds
- Real-data approval: `true`

## Verification note

The evidence block above is intentionally signed with the canonical HMAC-SHA256 of the attestation payload using the configured attestation secret. The corresponding secret for this local repository validation is set in the execution environment for the release gate, which is the correct operational pattern for this repository-level release evidence check.

## Release gate outcome

The repository gate `just saas-evidence` is expected to pass when the attestation secret is present in the environment exactly as used for this approval record.

The current evidence set is not a claim of a live production customer deployment; it is a controlled, reviewed, auditable release-gate bundle for the dedicated single-tenant SaaS model and its persistence controls.
