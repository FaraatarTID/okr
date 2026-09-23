Documentation HQ: [README](../../../README.md)

# T19 — Provisioned identity resolution

Status: production integration BLOCKED pending current target evidence and explicit ownership/authorization. This brief records safe preparation only.

## Existing evidence

- The 2026-09-20 one-row `admin` database count in D8 is historical, not current target evidence.
- `User.username` is unique, but current schema has no email, issuer, subject, or external identity-link column/table.
- `/v1/auth/me` resolves exact username; provisioning API accepts username, password, role, and profile fields without email or IdP subject.
- Local SaaS provisioning is metadata-only and cannot establish target customer account shapes.

See `task-T19-recon-report.md` for source locations and detailed findings.

## Safe contract outline

When production work is unblocked, resolve a cryptographically verified `(issuer, subject)` pair to exactly one existing provisioned user. Unlinked or ambiguous identities fail closed. Never fall back to email equality or create accounts just in time. Do not choose link cardinality, table/migration shape, or uniqueness constraints until current target counts and owner authorization establish them.

## Hard prerequisites before production code

1. Authorized current target recount of username/email shapes and identity-link uniqueness; confirm the invariant for the actual deployment.
2. Named identity/product owner approval for the link policy and legitimate account source.
3. Resolved migration-freeze path and explicitly authorized bootstrap/backfill.
4. D9 owner confirmation for `email_verified`; T18 verified-token contract; T23's approved identity architecture; then the T19 integration.

Until those facts exist, do not create a migration/backfill, session exchange route, email-based link, or generated OpenAPI/client/route-policy/auth-matrix changes. Fixture/design preparation only.