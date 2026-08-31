# ADR-001: Multi-Tenant Data Access Boundary

Documentation HQ: [README](../README.md)

Status: Accepted  
Date: 2026-08-31  
Owners: Architecture, Security, Operations

## Decision

Multi-tenant SaaS uses direct PostgreSQL access through the approved
transaction-mode pooler. The application resolves tenant identity from
server-side membership, sets `SET LOCAL app.tenant_id` as the first statement
of each request transaction, and relies on application predicates plus
PostgreSQL RLS as defense in depth.

The Supabase HTTPS fallback is restricted to alpha testing and selected
self-hosted deployments where direct database connectivity is unavailable. It
is not a SaaS fallback and must not be enabled for a multi-tenant SaaS
deployment.

## Context

The product's HTTPS fallback was introduced to unblock alpha testing when
Postgres ports were inaccessible. That constraint does not define the cloud
SaaS architecture. Under transaction pooling, a plain session `SET` could leak
tenant state across requests; `SET LOCAL` is safe only when set and consumed
inside the same transaction.

The HTTPS API path has no direct Postgres session and therefore cannot use
`current_setting('app.tenant_id')` as its RLS context. Supporting it in SaaS
would duplicate tenant filtering and authorization in another adapter, which
increases isolation and parity risk.

## Consequences

Positive:

- SaaS has one authoritative database isolation boundary.
- RLS can fail closed when an application filter is missed or tenant context is absent.
- Pooler-compatible transaction scope is explicit and testable.
- Alpha and self-hosted users retain the compatibility path that motivated the fallback.

Tradeoffs:

- SaaS deployments require network access to the approved Postgres pooler.
- A future SaaS HTTPS mode would be a new architecture decision, not a configuration toggle.
- Self-hosted HTTPS mode must maintain API-layer tenant filtering if multi-tenancy is enabled there.

## Required controls

- Every tenant-owned table has RLS enabled and forced, with a missing-context default-deny policy.
- The application role does not have `BYPASSRLS`.
- Every direct-Postgres request sets tenant context with `SET LOCAL` before tenant queries.
- Tests cover omitted context, pooled transaction isolation, cross-tenant denial, and same-tenant success.
- HTTPS fallback remains disabled by SaaS configuration policy.

## Reversal criteria

Reconsider this decision only when an enterprise requirement demonstrates that
SaaS cannot use the approved pooler. Reopening requires a new threat model,
quantified operational rationale, API-filter parity tests for reads, mutations,
jobs, and exports, plus explicit approval from security and architecture owners.
