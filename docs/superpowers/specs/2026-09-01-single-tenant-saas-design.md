# Single-Tenant Enterprise SaaS Design

Documentation HQ: [README](../../../README.md)

**Status:** Proposed design approved in principle by the owner on 2026-09-01.

## Goal

Evolve the working on-premise OKR application into an enterprise SaaS offering where each customer receives a dedicated application environment and dedicated database, while preserving the current on-premise deployment profile.

## Decision

Use a single-tenant deployment model for the first SaaS release. Each enterprise receives an isolated runtime, database, backup schedule, and operational boundary. A shared database with row-level security is explicitly deferred and is not required for the first SaaS release.

## Why this fits the product

- It matches the existing on-premise operating model.
- It provides a simple and strong customer-isolation story.
- It supports customer-specific backup and restore operations.
- It reduces the initial cross-tenant data-leakage risk.
- It supports enterprise requirements around data residency and operational ownership.
- It allows SaaS automation to be added around the existing application rather than requiring a rewrite.

## Deployment model

The product has three deployment profiles:

1. `on_premise`: one customer-operated environment, using the current deployment contract.
2. `single_tenant_saas`: one isolated application and database environment per enterprise, operated by the service provider.
3. `control_plane`: a small management layer that records customer environments, versions, health, backup state, and lifecycle actions. It does not contain customer OKR data.

Each customer environment contains the existing API, worker, BFF, web application, and database components. Customer data never needs to cross from one environment into another during normal operation.

## Control-plane responsibilities

The control plane owns:

- Customer and environment identity.
- Environment provisioning state.
- Deployment version and desired version.
- Health and readiness status.
- Backup policy, last successful backup, and restore-test status.
- Upgrade, rollback, suspend, and retire operations.
- Operator audit events for lifecycle actions.

The control plane must not become a proxy for ordinary customer-domain reads and writes. Customer application traffic goes directly to the customer environment after routing and authentication are established.

## Customer-environment responsibilities

Each environment owns:

- Customer authentication and authorization data.
- OKR domain data.
- Application sessions and revocation state.
- Background jobs and worker state.
- Customer-specific configuration that is safe to store locally.
- Database backup execution or provider-integrated backup target.

The existing BFF security controls, actor binding, session revocation, facade delegation, and import boundaries remain mandatory in every profile.

## Provisioning flow

1. An operator or approved control-plane workflow creates a customer record.
2. The control plane allocates an isolated environment identifier and target location.
3. Infrastructure creates the application runtime and dedicated database.
4. The environment runs the approved schema bootstrap and health checks.
5. The control plane registers the environment version, backup policy, and health state.
6. An operator completes an acceptance smoke test before the customer URL is activated.

Provisioning must be idempotent. Repeating a failed provisioning action must converge on one environment rather than create duplicate databases or runtimes.

## Upgrade and rollback flow

1. The control plane selects an application release artifact.
2. The artifact is deployed to one environment or a controlled pilot group.
3. Health, migrations, background jobs, and critical smoke tests are evaluated.
4. The release is promoted only after the environment meets its acceptance checks.
5. If the release is unhealthy, the environment returns to the previous application artifact.
6. Database changes must be backward-compatible during the application transition; destructive changes require a separately approved data lifecycle operation.

The first SaaS release must have a rehearsed application rollback using two real deployable artifacts. Database restore is a recovery operation, not the normal mechanism for routine application rollback.

## Backup and recovery

Before any real customer data is stored, each environment must have:

- Provider-supported automated backups.
- A defined retention period.
- Encrypted backup storage.
- An isolated restore procedure.
- A successful restore rehearsal.
- Documented RPO and RTO.
- A named operational owner.
- An audit record for backup and restore outcomes.

The disposable pre-SaaS database was exempt by explicit owner risk acceptance while it contained mock data; that data has been purged. The exemption is phase-limited and expires before the first real customer environment or persistent customer data is introduced. Production SaaS requires the backup/recovery controls listed above.

## Security boundary

The first SaaS release relies on environment isolation rather than shared-database RLS. The application must still enforce actor binding, session revocation, secure cookies, BFF origin controls, and backend authorization. Control-plane operators require separate privileged access and auditable lifecycle actions.

Cross-environment access must be denied by default. Support access, if later required, must be time-bound, explicitly authorized, scoped to one customer environment, and audited.

## Observability and operations

Every environment must expose:

- Liveness and readiness health.
- Version and schema revision information.
- Error and latency telemetry.
- Worker/job health.
- Backup freshness and restore-test status.
- Deployment and rollback events.

The control plane aggregates operational metadata, not customer OKR records. Alerts must identify the customer environment without exposing customer data in logs.

## On-premise compatibility

The current on-premise profile remains supported and must not depend on the control plane. Shared application services should use profile-specific adapters for provisioning, configuration, health reporting, and backup integration. Product-domain behavior should remain common unless a deployment-specific requirement is explicit.

## Delivery phases

### Phase 0: Stable pre-SaaS baseline

Freeze the promoted on-premise behavior, keep the runtime data disposable, retain the existing architectural gates, and prohibit implicit tenant/RLS scope.

### Phase 1: Environment contract

Define the customer-environment manifest, version contract, health contract, configuration contract, and lifecycle states without introducing a control plane yet.

### Phase 2: Repeatable single-tenant provisioning

Automate creation of one isolated application/database environment, idempotent bootstrap, initial operator smoke test, and retirement.

### Phase 3: Release operations

Add versioned artifacts, pilot deployment, health-gated promotion, application rollback rehearsal, and operator audit events.

### Phase 4: Production data readiness

Implement provider-backed backups, isolated restores, RPO/RTO reporting, retention, alerting, and an owner-approved recovery drill before onboarding real customers.

### Phase 5: Control plane

Add environment inventory, routing metadata, lifecycle APIs, health aggregation, backup status, and controlled operator actions. Keep customer-domain traffic out of the control plane.

### Phase 6: Enterprise readiness

Add customer-specific data residency, support access controls, compliance evidence, usage metering if needed, and commercial lifecycle integration.

## Explicitly deferred

- Shared-database multi-tenancy.
- PostgreSQL RLS for customer-domain isolation.
- Tenant identifiers in the current pre-SaaS domain schema.
- Real-customer data onboarding.
- Billing and self-service provisioning.
- Cross-customer analytics.

## Acceptance criteria for entering SaaS persistence work

The project may enter SaaS persistence work only when the owner approves a concrete customer environment contract, two deployable application artifacts exist for rollback, provisioning is repeatable, backups are provider-supported, restore has been rehearsed in isolation, RPO/RTO are documented, and an operational owner is named.
