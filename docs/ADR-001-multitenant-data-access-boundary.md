# ADR-001: Multi-Tenant Data Access Boundary

Documentation HQ: [README](../README.md)

Status: Rejected - permanently out of product scope (historical evidence)  
Date: 2026-08-31  
Owners: Architecture, Security, Operations

## Current product position

This ADR is retained as historical architecture evidence only. The product
does not support, and will not build, shared-database multi-tenancy or
PostgreSQL row-level security (RLS) as a SaaS isolation model.

The only supported SaaS model is a **dedicated single-tenant environment per
customer**, including a dedicated application deployment and database. Customer
isolation is provided by deployment and database boundaries, not by tenant rows
inside a shared database.

The multi-tenant/RLS decision recorded below is rejected and must not be
implemented, revived as deferred roadmap work, or treated as a prerequisite
for SaaS delivery. Any future change to the supported isolation model would
require a new architecture decision that explicitly supersedes this record.

## Decision

Shared-database multi-tenant SaaS using application tenant context,
tenant-scoped predicates, and PostgreSQL RLS is **rejected**.

SaaS deployments must instead provision one isolated application environment
and one isolated database for each customer. The application still requires
normal authorization, actor binding, session security, and audit logging, but
it must not introduce shared-database tenant/RLS machinery for customer
isolation.

## Context

The original proposal explored shared-database tenancy through a transaction-
mode pooler. It required resolving tenant identity from server-side membership,
setting `SET LOCAL app.tenant_id` for every request transaction, and maintaining
application predicates and RLS policies in parallel.

That complexity is unnecessary for the product's approved single-tenant-per-
customer operating model. Dedicated deployments and databases provide the
required isolation boundary without shared-database tenant context, RLS policy
drift, or cross-tenant query risk.

The Supabase HTTPS fallback remains available only for alpha testing and
selected self-hosted deployments where direct database connectivity is
unavailable. It is not a SaaS isolation strategy.

## Consequences

Positive:

- Each SaaS customer has an independent application and database boundary.
- SaaS authorization does not depend on shared-database tenant context or RLS.
- Provisioning, backup, recovery, and rollback can be performed per customer.
- Alpha and self-hosted users retain the compatibility path that motivated the fallback.

Tradeoffs:

- Operating a customer fleet requires per-environment provisioning and lifecycle automation.
- Dedicated environments use more infrastructure than a shared database.
- A shared-database SaaS model is intentionally unavailable, even if it could reduce infrastructure cost.

## Required controls for the supported model

- Every customer SaaS environment has its own database and credentials.
- Customer databases are not shared across SaaS environments.
- Per-application authorization, actor binding, session revocation, and audit logging remain mandatory.
- Provisioning, health checks, backup/recovery, and rollback operate per customer environment.
- HTTPS fallback remains disabled by SaaS configuration policy.

## Historical controls retained for traceability

The following controls belonged to the rejected shared-database design and are
retained here only to explain what was evaluated: transaction-scoped
`SET LOCAL app.tenant_id`, RLS enabled and forced on tenant-owned tables,
default-deny missing-context policies, no `BYPASSRLS`, and cross-tenant denial
tests. They are not implementation requirements for the supported SaaS model.

## Reopening policy

There is no planned reopening of this ADR. A proposal to introduce shared-
database multi-tenancy or RLS would require a new architecture decision, a new
threat model, quantified operational justification, and explicit approval from
the security and architecture owners. Until then, dedicated single-tenant
environments are the sole supported SaaS architecture.
