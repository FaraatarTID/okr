# Release Go/No-Go Checklist

Documentation HQ: [README](../../README.md)

Status: ACTIVE OPERATING CHECKLIST

## Purpose

This checklist governs the remaining operational slices after the repository-side architecture work is verified. It is intentionally fail-closed: no provider-backed rollout, migration, or customer-data handoff proceeds without the evidence below.

## Default decision

The default decision remains:
- supported topology: browser -> BFF -> backend API -> worker
- dedicated single-tenant model only
- no shared-database multi-tenancy or RLS tenant logic
- no direct browser-to-backend bypass without explicit exception

## Required evidence before go

### 1) Provider backup and restore evidence
- provider-supported backup selected and verified
- provider-issued backup ID recorded
- restore executed into an isolated non-production target
- provider-issued restore ID recorded
- integrity and cleanup evidence attached
- measured RPO/RTO captured and compared with target thresholds

### 2) Release rollback rehearsal
- two immutable release artifacts retained and hashed
- release promotion rehearsal performed
- rollback to previous known-good artifact executed
- health checks observed before and after rollback
- rollback duration recorded in seconds
- previous artifact retained for one release cycle

### 3) BFF operational evidence
- BFF route allowlist and security controls validated under provider topology
- provider-side ingress and request mediation verified
- health and failure-isolation evidence recorded
- paired BFF/backend rollback rehearsal attached

### 4) Performance evidence
- production-like deployment or provider environment available
- browser waterfall captured across browser, BFF, backend, and database path
- layer timings attached to the release record
- no speculative optimization claim without evidence

### 5) Ownership and signoff
- decision owner named and accountable
- platform or operations owner named and accountable
- operator identity attached to each operational action
- final signoff recorded before any broader rollout

## Go/No-Go matrix

| Area | Owner | Required evidence | Current status |
|---|---|---|---|
| Architecture and repo controls | Engineering lead | repository checks, boundary checks, topology checks | GO |
| Single-tenant provisioning contract | Platform/ops | environment identity, database resource ID, idempotent lifecycle | GO |
| Provider backup integrity | Platform/ops | provider-issued backup ID, checksum verification, backup freshness | NO-GO until verified |
| Isolated restore | Platform/ops | provider-issued restore ID, isolated target, integrity result | NO-GO until verified |
| Rollback rehearsal | Engineering lead + platform/ops | immutable artifact pair, rollback result, measured seconds | NO-GO until rehearsed |
| BFF deployment and mediation | Security + architecture | provider ingress, edge trust, failure isolation | NO-GO until evidenced |
| Performance | Engineering lead | browser waterfall and timing evidence | NO-GO until measured |
| Release signoff | Engineering lead | final owner signoff and attestation | NO-GO until signed |

## No-go triggers

Stop the rollout and escalate if any of the following occur:
- no provider-issued backup or restore ID exists
- backup or restore integrity is unverified
- rollback result is not measured and recorded
- BFF trust boundary is blurred or simplified without security evidence
- topology change is justified by convenience or latency alone
- repo checks are treated as production proof
- no named owner accepts the release decision

## Release gate summary

The release is allowed to proceed only when all of the following are true:
1. all required evidence is attached to the release record
2. all mandatory checks are green and tied to the same environment/customer identity
3. the final owner signoff is recorded
4. no open no-go trigger remains unresolved

## Current operational state

Repository-side controls are green. Provider-side rollout and recovery evidence remain the active gating items for broader production confidence and any customer-data onboarding beyond the controlled single-tenant evidence bundle.
