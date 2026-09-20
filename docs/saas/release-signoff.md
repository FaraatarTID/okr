# Production Persistence Release Signoff

Documentation HQ: [README](../../README.md)

## Signoff status

Status: BLOCKED - PROVIDER EVIDENCE PENDING
Date: 2026-09-14
Decision owner: engineering-owner
Operations owner: UNASSIGNED
Environment identity: env-a
Customer identity: customer-a
Release identity: release-rehearsal-a
Provisioning identity: provisioning-a

## Baseline and scope

This signoff approves the controlled single-tenant SaaS persistence entry gate under the repository operating model and fail-closed evidence contract.

Scope is limited to:
- dedicated application and database per customer
- single-tenant environment identity and provisioning
- provider-backed backup and isolated restore evidence
- immutable release/rollback evidence
- explicit named ownership and signed attestation

The scope explicitly excludes:
- shared-database multi-tenancy
- RLS or tenant isolation by schema sharing
- cross-customer data mixing
- any production customer-data onboarding not reflected in the approved evidence bundle

## Mandatory evidence references

- [phase-1-entry-evidence.md](phase-1-entry-evidence.md)
- [../operating-model-decision.md](../operating-model-decision.md)
- [../migration-rollback-runbook.md](../migration-rollback-runbook.md)
- [../architecture-status.md](../architecture-status.md)

## Approval statement

The decision owner has reviewed the repository contract. No production
approval is active: Hamravesh/Darkube provider evidence, a named operations
owner, and a verified attestation are still required.

## Attestation metadata

- Provider: UNSELECTED - Hamravesh/Darkube confirmation pending
- Backup ID: UNSELECTED
- Restore ID: UNSELECTED
- Artifacts:
  - release-0: sha256:0000000000000000000000000000000000000000000000000000000000000000
  - release-1: sha256:1111111111111111111111111111111111111111111111111111111111111111
- Measured rollback seconds: 45
- Measured RPO seconds: 60
- Measured RTO seconds: 120
- Attestation signature: UNSET

## No-go rule

Any deviation from the dedicated single-tenant model, any missing provider evidence, or any unapproved change to the backup/restore/rollback contract nullifies this approval until the evidence package is revalidated and re-signed.
