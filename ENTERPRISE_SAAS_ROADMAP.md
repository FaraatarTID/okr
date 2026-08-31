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

## Phase 0: SaaS architecture foundation

**Goal:** establish the security and domain foundations before exposing shared
cloud infrastructure to customers.

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
