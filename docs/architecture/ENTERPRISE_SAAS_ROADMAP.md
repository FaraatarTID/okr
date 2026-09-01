Documentation HQ: [README](../../README.md)

# Enterprise SaaS Roadmap

Status: ACTIVE
Decision: single-tenant enterprise SaaS first
Source design: [Single-Tenant Enterprise SaaS Design](../superpowers/specs/2026-09-01-single-tenant-saas-design.md)
Historical prerequisite: [Pre-SaaS Architecture Simplification Backlog](PRE_SAAS_ARCHITECTURE_BACKLOG.md)

## Product direction

Preserve the working on-premise OKR application and add managed SaaS operations around it. Each enterprise receives a dedicated application environment and dedicated database. A separate control plane manages customer environment inventory and lifecycle metadata; it does not proxy ordinary customer-domain traffic.

```text
Control plane -> provision, upgrade, monitor, suspend, retire

Customer environment A: spa-web -> spa-bff -> backend-api -> database
                                             -> backend-worker -> queue/storage

Customer environment B: spa-web -> spa-bff -> backend-api -> database
                                             -> backend-worker -> queue/storage
```

The current on-premise deployment remains supported and must not depend on the control plane. Shared-database SaaS and PostgreSQL RLS are deferred until a separate decision proves that dedicated environments are insufficient.

## Non-negotiable principles

1. Customer data is isolated by application and database environment.
2. Cross-environment access is denied by default.
3. Existing BFF security, actor binding, session revocation, authorization, worker, OpenAPI, and import-boundary controls remain mandatory.
4. Application artifacts are immutable; configuration and secrets are external.
5. Provisioning, upgrade, backup, restore, and retirement are repeatable and auditable.
6. Database backup and application rollback are mandatory before real customer data is introduced.
7. RLS and shared-database tenancy are future options, not Phase 0 scope.

## Phase gates

| Promotion | Required evidence | Decision owner |
| --- | --- | --- |
| Pre-SaaS -> Phase 0 | Promoted mainline, approved single-tenant topology, canonical startup, BFF decision, documentation cleanup, quality gates | Engineering owner and architecture reviewer |
| Phase 0 -> Phase 1 | Environment contract, version and health contracts, repeatable provisioning design, backup/rollback entry criteria | Engineering owner and operations reviewer |
| Phase 1 -> Phase 2 | Provisioning without manual SQL, pilot deployment, two deployable release artifacts, rollback rehearsal, backup/restore drill, RPO/RTO | Engineering owner and operations owner |
| Phase 2 -> Phase 3 | Signed enterprise requirement for identity, billing, residency, regional placement, or contractual isolation | Product owner plus security and operations reviewers |

Calendar time never promotes a phase. Missing evidence is work, not permission to skip the gate.

## Phase 0: SaaS environment foundation

Goal: define the dedicated customer-environment contract without changing the current product domain into a tenant-aware schema.

Deliverables:

- Customer-environment manifest and lifecycle state machine.
- Version, health, readiness, and configuration contracts.
- Dedicated application/database provisioning contract.
- Operator access and lifecycle audit-event contract.
- Backup, restore, retention, ownership, RPO, and RTO requirements.
- ADR recording single-tenant SaaS as the first deployment model.
- Explicit trigger and comparison criteria for any future shared-database/RLS ADR.

Exit criteria:

- An environment can be described without manual infrastructure assumptions.
- Provisioning, health, version, suspension, and retirement states are explicit.
- The on-premise profile still works independently.
- Real customer onboarding is blocked until backup and rollback evidence exists.

## Phase 1: Repeatable cloud environments

Goal: make one dedicated enterprise environment repeatable and operable.

Deliverables:

- Managed PostgreSQL, queue, cache, and object-storage adapters.
- Idempotent environment provisioning and retirement.
- Customer-specific configuration and secret-manager integration.
- Environment health and version reporting.
- Pilot deployment workflow with acceptance smoke tests.
- Application release rollback using two real deployable artifacts.
- Provider-supported backup and isolated restore rehearsal.

Exit criteria:

- An environment can be provisioned without manual SQL.
- A failed deployment can return to the previous application artifact.
- Backup freshness and restore-test status are visible to operators.
- Documented RPO/RTO targets are demonstrated by an operational drill.

## Phase 2: Enterprise identity and commercial lifecycle

Goal: support enterprise onboarding and account management.

Deliverables:

- OIDC login and enterprise SSO integration.
- SAML SSO for enterprise plans.
- SCIM provisioning and deprovisioning.
- MFA policy integration through the identity provider.
- Subscription plans, billing, quotas, and entitlements.
- Verified customer domains and environment routing.
- Customer administrator workflows separated from platform operations.

Exit criteria:

- Customer administrators manage membership without platform-operator access.
- Identity lifecycle changes revoke access promptly.
- Entitlements are enforced consistently in UI, API, and worker paths.

## Phase 3: Reliability, compliance, and scale

Goal: operate the service predictably across many dedicated environments.

Deliverables:

- Per-environment and platform-wide SLOs and alert routing.
- Tenant-aware audit and security investigation tooling.
- Rolling-version compatibility and expand/contract migration process.
- Backup, restore, export, deletion, and disaster-recovery drills.
- Rate limits and noisy-neighbor protection.
- Data residency and regional deployment policy.
- Cost and capacity model for dedicated environments.

Exit criteria:

- An environment incident can be isolated without taking down unrelated customers.
- Restore, deletion, and disaster-recovery evidence is repeatable and auditable.
- Capacity and cost signals support customer commitments.

## Control-plane boundary

The control plane owns customer and environment identity, desired/current version, health, backup state, lifecycle actions, and operator audit events. It must not own or proxy customer OKR records. Customer traffic is routed to the customer environment after authentication and environment resolution.

Provisioning must be idempotent. Repeating a failed action must converge on one environment rather than create duplicate application runtimes or databases.

## Self-hosted compatibility

On-premise deployments continue to use the existing supported deployment profiles. They share application contracts, authorization invariants, health checks, dependency checks, and operational documentation with SaaS, but they do not require the control plane or hosted billing.

## Deferred decisions

- Shared-database multi-tenancy and PostgreSQL RLS.
- Tenant identifiers in the current pre-SaaS domain schema.
- Database-per-tenant automation beyond the dedicated-environment contract.
- Regional deployment and data residency.
- Billing and self-service provisioning.
- Cross-customer analytics.
- Removing the BFF without a new ADR and security-parity evidence.

## Immediate execution sequence

1. Approve this roadmap and the linked single-tenant design.
2. Define the customer-environment manifest and lifecycle contract in [Customer Environment Contract](../saas/customer-environment-contract.md).
3. Build one repeatable isolated environment from the existing artifacts.
4. Add versioned deployment, health-gated promotion, and application rollback.
5. Add provider-backed backup/restore and document RPO/RTO before onboarding real data.
6. Add control-plane lifecycle automation only after one environment works manually and repeatably.
 
## Task 7 - Phase 1 entry-gate evidence and handoff (2026-09-01)

**Status: EVIDENCE ASSEMBLED; PHASE 1 PROMOTION BLOCKED**

The Task 1-6 implementation evidence is consolidated in [Phase 1 entry evidence](../saas/phase-1-entry-evidence.md). The approved first SaaS model remains single-tenant enterprise SaaS: one dedicated application environment and database per customer.

Entry-gate disposition:

- Environment contract, profile validation, isolated provisioning, release/rollback contracts, backup/restore contracts, and metadata-only control-plane inventory are implemented and locally tested.
- Local evidence is not production-provider evidence. No production SaaS environment, provider backup, provider restore, or customer-data onboarding is approved by this record.
- Application release rollback is demonstrated only through the isolated local adapter/test evidence. Provider-backed rollback: **NOT AVAILABLE - provider/artifact not selected**.
- Provider backup/restore evidence: **NOT AVAILABLE - provider/artifact not selected**. Local metadata-only contract evidence does not substitute for provider evidence.
- Provider checksum verification, retention enforcement, measured RPO/RTO, and provider restore timing: **NOT AVAILABLE - provider/artifact not selected**.
- Real-data onboarding is prohibited until the provider-specific backup/restore and application rollback gates are evidenced and owned.
- Shared-database tenancy, tenant identifiers, RLS, and cross-customer schema remain deferred.

Required owners before production entry:

- Product/architecture owner: repository owner, for gate acceptance and scope decisions.
- Platform/operations owner: **UNASSIGNED**; must be named before provider integration and production onboarding.
- Customer-environment operator: must be named for each lifecycle and recovery action.

The pre-SaaS baseline remains supported and may continue product implementation without tenant/RLS or real-data scope.

The executable promotion gate is `just saas-evidence`. It must pass against
`../saas/phase-1-entry-evidence.md` before Phase 1 promotion; the current
document is intentionally incomplete and therefore must fail closed. The
canonical deployment vocabulary is `on_premise`, `single_tenant_saas`, and
external `control_plane`; `self_hosted` and `saas` are compatibility aliases
only at explicitly tested legacy boundaries.

Lifecycle commands use authenticated operator credentials, not arbitrary
operator-name arguments. The token is supplied through `OKR_OPERATOR_TOKEN`
and resolved against the credential file passed to the command or configured
through `OKR_OPERATOR_CREDENTIAL_FILE`.


