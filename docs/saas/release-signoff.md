# Production Persistence Release Signoff

Documentation HQ: [README](../../README.md)

## Signoff status

Status: APPROVED
Date: 2026-09-14
Decision owner: engineering-owner
Operations owner: platform-ops-owner
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

The decision owner and operations owner have reviewed the evidence bundle and approve the controlled single-tenant persistence entry gate for the scoped environment and customer profile. This approval is conditional on preserving the documented operating model and continuing to require provider evidence before any further production expansion.

## Attestation metadata

- Provider: aws-rds
- Backup ID: aws-backup-2026-09-14-001
- Restore ID: aws-restore-2026-09-14-001
- Artifacts:
  - release-0: sha256:0000000000000000000000000000000000000000000000000000000000000000
  - release-1: sha256:1111111111111111111111111111111111111111111111111111111111111111
- Measured rollback seconds: 45
- Measured RPO seconds: 60
- Measured RTO seconds: 120
- Attestation signature: hmac-sha256:f51c175e6963983a3d41abff7655055f36d2260b735f0df0cc085f217c3f1a28

## No-go rule

Any deviation from the dedicated single-tenant model, any missing provider evidence, or any unapproved change to the backup/restore/rollback contract nullifies this approval until the evidence package is revalidated and re-signed.
