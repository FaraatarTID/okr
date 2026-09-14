Documentation HQ: [README](../README.md)

# Working Guide

Use this as the compact starting point for continuing work.

## Primary guide

- [docs/architecture/ENTERPRISE_SAAS_ROADMAP.md](architecture/ENTERPRISE_SAAS_ROADMAP.md)

This is the main roadmap and the best single document to anchor work.

## Status ledger

- [docs/architecture-status.md](architecture-status.md)

This shows what is already verified and what remains open.

## Security and boundary references

- [docs/bff-security-review.md](bff-security-review.md)
- [docs/bff-boundary-adr.md](bff-boundary-adr.md)
- [docs/architecture-boundaries.md](architecture-boundaries.md)

## Release and operational gates

- [docs/saas/release-go-no-go-checklist.md](saas/release-go-no-go-checklist.md)
- [docs/saas/prerelease-runbook.md](saas/prerelease-runbook.md)

## Current working posture

The repo-side architecture and trust boundary are verified. The remaining blocker for production SaaS/customer-data work is operational evidence, not a missing code-level architecture decision.

Current gating items remain:

- provider-backed backup and isolated restore evidence
- measured RPO/RTO
- provider-backed rollback rehearsal
- named platform/operations owner
- explicit production customer-data approval

## Decision rule

When unsure, follow this order:

1. Roadmap
2. Architecture status ledger
3. Targeted security or operational doc
4. Code and tests

The roadmap is the source of intent; the status ledger is the source of truth for current state; the support docs are the implementation detail and evidence references.
