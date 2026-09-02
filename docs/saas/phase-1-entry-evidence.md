# SaaS Phase 1 Entry Evidence

Documentation HQ: [README](../../README.md)

**Date:** 2026-09-01  
**Decision:** Evidence assembled; Phase 1 promotion blocked  
**Scope:** Task 1-6 completion and handoff

## Executive disposition

The first SaaS model is approved in principle as **single-tenant enterprise SaaS**: each enterprise receives a dedicated application environment and dedicated database. Task 1-6 implementation evidence establishes the local contracts and safety boundaries needed to continue platform work. It does **not** establish production SaaS readiness and does not authorize real customer-data onboarding.

The current identifiers are contract/test fixtures, not live environments:

- Environment: `env-a`
- Customer: `customer-a`
- Database target: a dedicated target represented by the environment manifest
- Application artifacts: synthetic `release-0` and `release-1`, each required to use SHA-256-pinned image references

## Evidence matrix

| Area | Evidence from Task 1-6 reports | Disposition |
|---|---|---|
| Environment contract | Versioned manifest, required environment/customer identity, dedicated database target, lifecycle states and explicit transitions | Implemented and focused-tested locally |
| Profile safety | SaaS profile requires identity and database mode; Supabase/API fallback is rejected; Compose propagates profile metadata | Implemented and focused-tested locally |
| Provisioning | Provider-neutral ports, persistent local disposable adapter, matching-identity idempotency, conflict rejection, suspend/retire lifecycle | Implemented and focused-tested locally |
| Provisioning identifiers | `env-a` and `customer-a` are representative fixtures; no real customer environment was provisioned | Not production evidence |
| Provisioning idempotency | Repeat provision returns the existing environment with `created=false` and one create call; persisted CLI processes provision, suspend, retire, and later idempotent retire with `changed=false` | Local disposable evidence |
| Health gate | Release promotion is health-gated; failed health restores the previous artifact in the isolated adapter | Local rollback evidence only |
| Release rollback | Separately registered `release-0` and `release-1` synthetic artifacts, immutable digest checks, environment binding, durable local deployment records | Local adapter/test evidence; provider rollback **NOT AVAILABLE - provider/artifact not selected** |
| Backup contract | Provider and restore interfaces, provider-issued identifier requirement, checksum, retention, RPO/RTO, operator, freshness, and isolated-target fields | Contract implemented and locally tested |
| Backup/restore evidence | `LocalBackupProvider` creates/verifies metadata for `env-a`, registers isolated target `rehearsal-db-1`, and records a verified restore; checksum-failure state is persisted at `.test-artifacts/backup-checksum-failure.json` | Local evidence only |
| RPO/RTO | RPO/RTO are required recorded targets and restore duration is represented by the contract | Production measurements not evidenced |
| Control plane | Metadata-only inventory, lifecycle audit, operator authorization, release/backup metadata, customer-domain boundary | Implemented and focused-tested locally |

## Exact focused test evidence reported

- Task 1 final: `22 passed` (`tests/test_customer_environment_contract.py`).
- Task 2 final: `27 passed` (`tests/test_saas_environment_config.py`).
- Task 3 final: `14 passed` (`tests/test_saas_provisioning.py`).
- Task 4 final: `13 passed` (`tests/test_saas_release_operations.py`).
- Task 5 final: `18 passed` (`tests/test_saas_backup_operations.py`).
- Task 6 final: `34 passed` for the paired control-plane and boundary evidence.

These are the exact final counts reported by the task implementers/reviewers. They are evidence of the scoped local implementation, not a production certification.

## Synthetic release fixture evidence

- `release-0`: `sha256:dc653afb00e8d53f9c94ff5f1bbec0de9ad7f76889af79f46efe9356b95c02fd`
- `release-1`: `sha256:c2e19570b6aee82937bf4b09640059646a6985f80b1b16b91924f92a751a75a0`

The test helper hashes the strings `sha256:release-0` and `sha256:release-1`; these are synthetic fixture digests and are not evidence of immutable registry artifacts.

## Local backup/restore evidence

- Provider: `LocalBackupProvider` (test-only, metadata-only).
- Environment: `env-a`.
- Backup identifier: generated `provider-backup-*` identifier; no provider-issued production identifier exists.
- Restore target: registered isolated `rehearsal-db-1`.
- Result: checksum verification passed; isolated restore returned `verified=True` and recorded non-negative elapsed/RTO measurements.
- Failure-state evidence: checksum failure persisted at `.test-artifacts/backup-checksum-failure.json`.
- Production provider backup/restore: **NOT AVAILABLE - provider/artifact not selected**.

## Entry gates and owners

Before production SaaS or real customer data, all of the following must have evidence:

- **Provider backup:** Platform/operations owner selects the provider-supported backup mechanism and records a provider-issued backup identifier. Current state: **NOT AVAILABLE - provider/artifact not selected**.
- **Restore:** Assigned operator restores into a registered isolated target, verifies integrity, records cleanup, and preserves provider evidence. Live/production targets remain prohibited for rehearsal.
- **RPO/RTO:** Platform/operations owner records approved targets and measured backup freshness, restore duration, and observed recovery results.
- **Application rollback:** Assigned operator rehearses provider-backed deployment of two immutable artifacts, health-gated promotion, and rollback, preserving the deployment record. Current state: **NOT AVAILABLE - provider/artifact not selected**.
- **Operational ownership:** Project/repository owner is the decision owner for scope and gate decisions; platform/operations owner: **UNASSIGNED**; each operation must identify its authenticated operator.
- **Control-plane authorization:** Production requires a non-empty `OKR_CONTROL_PLANE_OPERATORS` allowlist; the admin compatibility fallback is retained only for explicit non-production/on-premise operation.
- **Real-data approval:** Product/architecture owner explicitly approves onboarding only after the preceding evidence is reviewed.

## Explicit gaps and deferrals

- Production backup provider, provider restore, retention enforcement, freshness monitoring, and measured production RPO/RTO: **NOT AVAILABLE - provider/artifact not selected**.
- Provider-backed application deployment rollback: **NOT AVAILABLE - provider/artifact not selected**.
- No production customer environment exists in this evidence set.
- The current database is disposable/mock-data pre-SaaS state; its emptiness is not a recovery control.
- Shared-database tenancy, tenant identifiers, RLS, and cross-customer schema are permanently out of scope. Dedicated single-tenant isolation is the only approved SaaS model.
- Phase 1 promotion and real-data onboarding are explicitly blocked until the provider-specific gates above are closed.

## Required evidence-field check

The machine-readable evidence contract consumed by `just saas-evidence` is:

```json
{
  "schema_version": 1,
  "decision": {"status": "BLOCKED", "owner": "UNASSIGNED"},
  "provisioning": {"environment_id": "env-a", "customer_id": "", "provisioning_identity": "", "idempotent": true},
  "release": {"artifacts": [], "release_identity": "", "rollback_result": "not evidenced"},
  "backup": {"provider": "", "backup_id": "", "backup_target": "", "verified": false},
  "restore": {"result": "not evidenced", "target": ""},
  "rpo_rto": {"measured_rpo_seconds": null, "measured_rto_seconds": null},
  "owners": {"decision": "UNASSIGNED", "operations": "UNASSIGNED"},
  "real_data_approval": false,
  "attestation": {
    "provider": "",
    "backup_id": "",
    "restore_id": "",
    "environment_id": "",
    "customer_id": "",
    "backup_target": "",
    "release_identity": "",
    "provisioning_identity": "",
    "artifact_digests": [],
    "measured_rollback_seconds": null,
    "measured_rpo_seconds": null,
    "measured_rto_seconds": null,
    "decision_owner": "UNASSIGNED",
    "operations_owner": "UNASSIGNED",
    "signature": ""
  }
}
```

The attestation section is intentionally incomplete. The executable gate requires a non-local provider, provider-issued backup and restore IDs, environment/customer identity, backup target, release and provisioning identities, two immutable artifact digests, numeric measured rollback/RPO/RTO values, named owners, and an HMAC-SHA256 signature verified with the configured attestation secret. Every attested identity and measurement is included in the signed canonical payload and must exactly match the corresponding structured evidence field. Headings or marker-only prose cannot satisfy the gate.

## Handoff decision

Continue implementation of the single-tenant platform contracts and local automation, but keep Phase 1 promotion blocked. Do not claim production SaaS readiness, do not onboard real customer data, and do not begin shared-database RLS work as part of this phase.

The executable gate is `just saas-evidence` (or `python scripts/check_saas_phase1_evidence.py`). It is expected to fail for this document until provider-backed evidence and named operations ownership are supplied.
