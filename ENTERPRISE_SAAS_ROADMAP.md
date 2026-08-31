Documentation HQ: [README](README.md)

# Enterprise SaaS Roadmap

Current roadmap for delivering OKR as a cloud SaaS while preserving a
supported enterprise self-hosted deployment option.

## Product direction

OKR is an enterprise, multi-user platform. The SaaS offering adds managed
provisioning, tenant isolation, identity integration, billing, and cloud
operations to the existing SPA-first runtime:

```text
Browser -> CDN/WAF -> spa-web -> spa-bff -> backend-api
                                             |       |
                                             v       v
                                      PostgreSQL  backend-worker
                                      Redis/queue  object storage
```

The same application artifacts should support SaaS and self-hosted delivery.
Deployment-specific infrastructure belongs behind explicit adapters and
configuration, not in product behavior or tenant authorization logic.

## Non-negotiable SaaS principles

1. Tenant identity is derived from authenticated server-side membership, never
   trusted from a client-supplied `tenant_id`.
2. Every tenant-owned read, write, job, file, and audit event is tenant-scoped.
3. PostgreSQL Row-Level Security is defense in depth, not a replacement for
   application authorization.
4. API and worker processes are stateless and horizontally disposable.
5. Runtime configuration and secrets are externalized from immutable artifacts.
6. SaaS and self-hosted modes share contracts, tests, migrations, and security
   invariants wherever possible.
7. Multi-tenant SaaS uses direct Postgres through the approved transaction
   pooler; the Supabase HTTPS fallback is restricted to alpha and self-hosted
   compatibility deployments.

## Planning controls

### Capacity and effort estimates

Estimates assume one primary maintainer working sequentially, with 12-16
focused engineering hours per week after support, release operations, and
incident reserve. Each estimate includes implementation, tests, documentation,
and one correction loop. It excludes customer decision latency, procurement,
and cloud-provider lead time.

| Phase | Estimate | Capacity envelope | Commitment |
| --- | ---: | ---: | --- |
| Phase 0: SaaS architecture foundation | 8-12 sessions / 64-96 hours | 5-8 weeks | Committed prerequisite |
| Phase 1: Cloud runtime and control plane | 10-16 sessions / 80-128 hours | 6-10 weeks | Conditional on Phase 0 |
| Phase 2: Enterprise identity and commercial lifecycle | 12-20 sessions / 96-160 hours | 8-13 weeks | Conditional on evidence |
| Phase 3: Regional, compliance, and advanced scale | 16-28 sessions / 128-224 hours | 10-18 weeks | Contract-triggered only |

These are planning ranges, not delivery promises. Work that exceeds its upper
bound is split into a smaller slice or returned to architecture review instead
of silently expanding the phase.

### Phase promotion gates

| Promotion | Required evidence | Decision owner |
| --- | --- | --- |
| Phase 0 -> Phase 1 | Server-derived tenant identity; application and database cross-tenant denial tests; tenant context preserved in jobs, retries, exports, and audit events; no open critical/high isolation findings | Engineering owner and security reviewer |
| Phase 1 -> Phase 2 | Tenant lifecycle works without manual SQL; load baseline identifies a real scaling constraint; two release cycles of usable SLO/error-budget data; rollback and backup/restore drills recorded | Engineering owner and operations owner |
| Phase 2 -> Phase 3 | Signed enterprise requirement for residency, regional placement, or contractual isolation; quantified tenant/traffic demand; approved ADR, threat model, and cost model | Product owner plus security, legal, and operations reviewers |

Calendar time alone never promotes a phase. If a gate is not met, capacity is
spent closing the gate or addressing observed production risk.

### Tenancy ADR starting bias

The shared-database versus database-per-tenant ADR should begin with an
explicit default leaning: shared PostgreSQL with mandatory tenant-scoped
application authorization, database constraints/RLS as defense-in-depth, and
automated cross-tenant denial tests. This is the most supportable starting
point for a solo maintainer and preserves one coherent SaaS/self-hosted model.

The ADR must overturn that default when contractual isolation, data residency,
noisy-neighbor limits, backup/restore requirements, or blast-radius analysis
show that shared infrastructure is insufficient. Database-per-tenant remains a
valid option, but it must be selected deliberately after comparing migration
cost, operational burden, failure isolation, restore time, observability, and
maximum expected tenant count.

The same ADR records the data transport boundary: SaaS tenant traffic uses the
direct Postgres path so transaction-local RLS context is available. HTTPS
fallback remains an explicit alpha/self-hosted capability. It is not enabled
for SaaS by default and cannot be introduced there without a new threat model,
API-layer filtering parity tests, and architecture approval.

### Commitment vocabulary

- `Committed`: required for the next phase and covered by the current capacity envelope.
- `Conditional`: begins only after its promotion gate has objective evidence.
- `Contract-triggered`: begins only after a signed customer or regulatory requirement.
- `Deferred`: documented for future evaluation and receives no current implementation capacity.

## Phase 0: SaaS architecture foundation

**Goal:** establish the security and domain foundations before exposing shared
cloud infrastructure to customers.

### Existing foundations to transfer

Phase 0 should extend proven mechanisms rather than replace them:

- The centralized authorization layer, including `_authorize_goal_mutation` and the owner/manager/admin predicates in `src/domain/authorization.py`, should gain tenant-aware predicates and context checks.
- The mutation authorization matrix in `test_backend_mutation_auth_matrix.py` should be extended so every tenant-sensitive route proves both BFF exposure policy and cross-tenant denial behavior.
- Fail-closed mutation behavior under transport failure remains a non-negotiable isolation property: uncertain tenant or data state must refuse writes.
- Durable job state, idempotency keys, and retry classification should be retained; tenant context must be carried through enqueue, retry, execution, and dead-letter handling.
- OpenAPI export, generated client types, and the CI drift gate should remain the contract enforcement path as tenant-scoped fields and responses are introduced.

### Genuinely greenfield scope

There is currently no tenant concept, membership model, or tenant-specific RLS
policy. The following work is therefore domain-model construction, not merely
plumbing:

- Define tenant identity, membership, lifecycle, and server-side context resolution.
- Build the tenant coverage inventory for every persisted entity, including ownership, foreign keys, uniqueness, indexes, and retention rules.
- Reconcile current instance-wide semantics for cycles, teams, and users with tenant-local semantics. In particular, “global” cycles and admin-owned records must be classified as tenant-owned, platform-owned, or explicitly shared before migrations are written.
- Add migration and denial-test fixtures that prove a record from tenant A cannot be read, mutated, exported, or processed by tenant B.

This distinction is a Phase 0 scope guard: existing reliability patterns are
reused, while the tenant data model receives its own design, migration review,
and threat-model sign-off before cloud scaling work begins.

Deliverables:

- `organization`/tenant and membership model
- Tenant context middleware for BFF and backend
- Tenant-aware authorization service and request metadata
- `tenant_id` coverage inventory for every persisted entity
- Cross-tenant denial tests for read, mutation, job, and export paths
- ADR documenting shared-database versus database-per-tenant strategy

Exit criteria:

- No tenant-owned request can execute without resolved tenant membership.
- Cross-tenant access is denied in application tests and database policy tests.
- Background jobs retain tenant context through enqueue, retry, and execution.

## Phase 1: Cloud runtime and control plane

**Goal:** make tenant lifecycle and cloud deployment operationally explicit.

Deliverables:

- Managed PostgreSQL, Redis, queue, and object-storage adapters
- Tenant provisioning, suspension, deletion, and export workflows
- Platform operator control plane separated from customer administration
- Per-tenant quotas, feature flags, and usage counters
- Cloud secret manager integration and signing-key rotation
- Stateless API/BFF/worker deployment with autoscaling boundaries

Exit criteria:

- A tenant can be provisioned and made usable without manual SQL.
- A suspended tenant cannot authenticate or enqueue work.
- API and worker replicas can scale independently without local state coupling.

## Phase 2: Enterprise identity and commercial lifecycle

**Goal:** meet enterprise customer onboarding and account-management needs.

Deliverables:

- OIDC login and tenant-aware session claims
- SAML SSO for enterprise plans
- SCIM provisioning and deprovisioning
- MFA policy integration through the identity provider
- Subscription plans, billing provider integration, quotas, and entitlements
- Tenant domain discovery and verified custom domains

Exit criteria:

- Customer administrators can manage membership without platform-operator access.
- Identity lifecycle changes revoke access promptly.
- Entitlements are enforced consistently in UI, API, and worker paths.

## Phase 3: SaaS reliability, compliance, and scale

**Goal:** operate the service predictably across tenants and regions.

Deliverables:

- Per-tenant and platform-wide SLOs, dashboards, and alert routing
- Tenant-aware audit events and security investigation tooling
- Expand/contract migration process with rolling-version compatibility
- Backup, restore, tenant export, and tenant deletion drills
- Rate limits and noisy-neighbor protection by tenant and plan
- Data residency and regional deployment policy
- Disaster recovery exercise with documented RPO/RTO evidence

Exit criteria:

- A tenant incident can be isolated without taking down unrelated tenants.
- Restore and deletion evidence is repeatable and auditable.
- SLO and capacity signals support capacity planning and customer commitments.

## Self-hosted compatibility track

Self-hosted enterprise deployments remain supported through Docker Compose,
Kubernetes, or VM-based deployment. They must use the same:

- OpenAPI and BFF contracts
- Tenant and authorization invariants
- Migration and readiness gates
- Dependency lockfiles and security checks
- Backup, audit, and operational runbooks

Cloud-only capabilities such as hosted billing or managed identity may be
disabled or replaced by deployment adapters, but must not weaken tenant
isolation or authorization.

## Immediate backlog promotion

The following work should be promoted from deferred architecture planning:

1. Tenant/workspace data model and authenticated tenant context
2. Tenant-aware authorization and PostgreSQL RLS
3. Tenant propagation through async jobs, exports, and audit events
4. SaaS control-plane provisioning lifecycle
5. Managed infrastructure adapters and cloud deployment target

Do not begin broad package relocation or Turborepo/Nx adoption before Phase 0
tenant boundaries are designed and tested.
