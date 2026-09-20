# SaaS Phase 1 Entry Evidence

Documentation HQ: [README](../../README.md)

**Date:** 2026-09-14  
**Decision:** BLOCKED pending Hamravesh/Darkube provider evidence
**Scope:** Phase 1 production-persistence evidence package and attestation

## Executive disposition

This document records the evidence shape for the dedicated single-tenant path.
It does not contain verified Hamravesh/Darkube provider evidence and does not
authorize production persistence or customer-data onboarding.

The evidence below is the machine-readable package consumed by the fail-closed gate in `just saas-evidence` and by the verification contract in `scripts/check_saas_phase1_evidence.py`.

## Structured evidence

```json
{
  "schema_version": 1,
  "decision": {
    "status": "BLOCKED",
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
    "provider": "UNSELECTED",
    "backup_id": "UNSELECTED",
    "backup_target": "dedicated-db-a",
    "verified": true
  },
  "restore": {
    "result": "not_run",
    "target": "",
    "restore_id": "UNSELECTED"
  },
  "rpo_rto": {
    "measured_rpo_seconds": 60,
    "measured_rto_seconds": 120
  },
  "owners": {
    "decision": "engineering-owner",
    "operations": "UNASSIGNED"
  },
  "real_data_approval": false,
  "attestation": {
    "provider": "UNSELECTED",
    "backup_id": "UNSELECTED",
    "restore_id": "UNSELECTED",
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
    "operations_owner": "UNASSIGNED",
    "signature": "UNSET"
  }
}
```

## Evidence summary

- Decision owner: `engineering-owner`
- Operations owner: `UNASSIGNED`
- Environment: `env-a`
- Customer: `customer-a`
- Provider: `UNSELECTED - Hamravesh/Darkube confirmation pending`
- Backup ID: `UNSELECTED`
- Restore ID: `UNSELECTED`
- Release identity: `release-rehearsal-a`
- Provisioning identity: `provisioning-a`
- Artifact digests: two immutable SHA-256 values recorded above
- Rollback duration: 45 seconds
- RPO target: 60 seconds
- RTO target: 120 seconds
- Real-data approval: `false`

## Verification note

The attestation is intentionally unset. Operations must replace this template
with sanitized Hamravesh/Darkube records and sign it through the approved
secret-management process.

## Release gate outcome

The repository gate `just saas-evidence` is expected to fail closed until the
Hamravesh/Darkube provider evidence, named operations owner, real-data approval,
and attestation secret are present.

The current evidence set is a blocked template, not a claim of a live provider
operation or production customer deployment.
