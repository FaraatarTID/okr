# Phase 0 Backlog - Multi-Tenant Security and Domain Foundation

Documentation HQ: [README](../../README.md)

Status: ACTIVE - P0-00 performance recovery in progress  
Scope: tenant model, authorization boundary, data isolation, and migration safety  
Planning horizon: 8-17 weeks at 12-16 focused hours per week  
Owner model: one primary maintainer, with an independent named security reviewer at the exit gate

## Purpose

Phase 0 establishes the security and domain foundation required before shared
cloud infrastructure, enterprise onboarding, or horizontal scaling. It is a
greenfield domain change inside an existing reliable platform: proven
authorization, fail-closed mutation, job durability, contract governance, and
test-matrix patterns are reused; tenant identity and isolation are new.

## Non-negotiable invariants

- Tenant identity is resolved from authenticated server-side membership, never from a client-supplied `tenant_id`.
- Every tenant-owned read, write, export, file, job, retry, and audit event is tenant-scoped.
- Authorization is enforced in the application layer; RLS and database constraints provide defense in depth.
- RLS is established before tenant-scoped feature delivery and exists on every tenant-owned table; a missed application filter must fail closed at the database boundary.
- Missing or ambiguous tenant context fails closed.
- A migration is not complete until legacy/global semantics are classified and denial tests cover the new boundary.
- SaaS and self-hosted modes share contracts, migrations, security invariants, and tests.

## Root-cause model

The current product has a reliable authorization discipline but no tenant
concept. Users, teams, and cycles are modeled around one flat instance, so
“global” currently means the whole deployment. If infrastructure is scaled
before this meaning is changed, isolation becomes an after-the-fact filter and
creates a cross-tenant leakage risk in reads, jobs, exports, and audit trails.

## Initial tenant coverage inventory

This is the Phase 0 starting inventory from `src/models.py`. It must be
validated against migrations, queries, exports, and worker payloads before the
schema migration is authored.

### Root tenant-owned tables

These tables require a direct `tenant_id` foreign key to the new
`organization` table:

- `Team`: replace globally unique `name` with tenant-scoped uniqueness `(tenant_id, name)`.
- `User`: add tenant ownership; usernames and other identifiers require an explicit tenant/global uniqueness decision.
- `Cycle`: preserve `ux_cycle_owner_active` semantics while folding `tenant_id` into the active-cycle invariant.
- `Goal`: add tenant ownership alongside the existing `goal.owner_id` authorization anchor.

### Child tenant-owned tables

These tables should carry a direct `tenant_id`, even when they already point to
a tenant-owned parent. Do not make RLS walk a multi-table hierarchy to infer
tenant scope:

- `Objective`
- `KeyResult`
- `Task`
- `WorkLog`
- `WeeklyPlan`
- `CheckIn`
- `Experiment`
- `RetroExperimentOutcome`
- `AlignmentEdge`
- `ObjectiveAlignmentLink`
- `Retrospective`

Direct columns make coverage auditable through `information_schema`, keep RLS
predicates simple, and allow tenant-scoped indexes and constraints without
repeated joins. Application writes must validate that parent and child tenant
identities match.

### Cross-cutting tables

- `AsyncJob`: add `tenant_id` directly. Existing nullable `team_id` and `actor_username` do not provide tenant scope; enqueue, claim, retry, requeue, and execution need explicit propagation.
- `AuditEvent`: add `tenant_id` and tenant-scoped indexes. Existing actor indexes are insufficient for tenant investigation and require a migration/backfill plan.
- `AuthThrottleState`: verify whether keys are user-scoped or can collide across tenants; define the key contract before tenant onboarding.

The enum classes (`TaskStatus`, `UserRole`, `MetricType`, and similar) remain
system-wide and require no tenant column.

### Inventory priority

`AsyncJob` and `AuditEvent` are the first inventory targets because they have no
tenant-shaped field to extend and cross request boundaries. The OKR hierarchy
can extend its existing authorization chain, but worker and audit paths must be
designed from scratch for tenant propagation.

## Existing foundations to extend

- Extend `src/domain/authorization.py`, including `_authorize_goal_mutation` and owner/manager/admin predicates, with tenant-aware context checks.
- Extend `test_backend_mutation_auth_matrix.py` so tenant-sensitive routes prove both BFF policy coverage and cross-tenant denial.
- Preserve fail-closed mutation behavior during transport uncertainty or missing tenant context.
- Carry tenant context through existing durable job state, idempotency keys, retry classification, and dead-letter handling.
- Add tenant fields to OpenAPI schemas and generated client contracts so the existing drift gate protects the new boundary.
- Write database-level cross-tenant denial tests before implementing each tenant-sensitive capability, using the same route/test pairing discipline as the mutation authorization matrix.

## Genuinely greenfield scope

- Define tenant identity, membership, lifecycle, and server-side context resolution.
- Build the tenant coverage inventory for every persisted entity, including ownership, foreign keys, uniqueness, indexes, and retention rules.
- Reconcile current instance-wide semantics for cycles, teams, and users with tenant-local semantics. “Global” cycles and admin-owned records must be classified as tenant-owned, platform-owned, or explicitly shared before migrations are written.
- Add migration and denial-test fixtures proving a record from tenant A cannot be read, mutated, exported, or processed by tenant B.

## Work packages

### P0-00 - Performance baseline and load-time recovery

Finding: The application can take approximately 10 seconds to load page data,
which is unacceptable when individual Supabase calls are expected to be below
roughly 400 ms. This is a production-blocking system problem and must be
understood before tenant work adds another per-row policy dimension.

Root cause hypothesis: the delay may be a request waterfall, duplicate/fan-out
fetching, expensive work inside an already-consolidated snapshot, transport
queueing, fallback/circuit-breaker behavior, or a Supabase free-tier cold start.
The trace must identify the actual critical path before optimization begins.

Verified implementation findings and completed recovery work:

- The Atlas hierarchy read is already set-based: it loads goals, objectives,
  key results, and tasks through bounded collection queries rather than ORM
  lazy traversal. A generic eager-loading rewrite is therefore not required
  unless tracing identifies a different page or query path.
- The ritual-mode frontend previously issued one experiment request per key
  result after receiving the snapshot. That fan-out has been removed; the
  frontend now groups experiments already returned by the consolidated ritual
  snapshot.
- The BFF already behaves as a pass-through for backend payloads; page-specific
  response aggregation is not currently a confirmed source of delay.
- Independent bootstrap reads already use parallel orchestration in the
  affected Atlas hooks. Further parallelization should be driven by a trace,
  not by broad refactoring.
- The initial Atlas snapshot request no longer waits behind an artificial
  200-millisecond timer.
- Raw `ai_analysis` is now requested only for Atlas inspector mode. Other views
  receive derived AI fields without the larger analysis blobs.

These are code-level fixes, not a substitute for an end-to-end browser trace.
The remaining P0-00 gate is to measure the real critical path and establish
warmed and cold-start budgets before declaring the package closed.

Tasks:

- Capture a browser waterfall and end-to-end trace for the slowest page.
- Confirm whether the page uses the consolidated `ritual.snapshot` RPC or Atlas snapshot path; if so, inspect work inside and around that single request before assuming N+1 behavior.
- Record request count, dependency order, BFF time, backend time, database query count/time, serialization time, and client render time.
- Log the serving data-access strategy for each request: direct TCP or HTTPS fallback.
- Record HTTPS fallback semaphore wait time and queue depth; distinguish parallel callers waiting behind the default four-call limit from database latency.
- Record TCP probe state, circuit-breaker state/cooldown, retry delay, and fallback transition time.
- Test a cold request after Supabase free-tier inactivity separately from warmed steady-state requests.
- Fix hierarchy traversal first: eager-load Goal -> Objective -> KeyResult -> Task with `selectinload`/`joinedload`, or replace the traversal with a bounded recursive CTE/snapshot query, and prove the query count does not grow with node count.
- Stop recomputing Goal/Objective rollups on reads; maintain stored rollup values at check-in and task-progress write boundaries, with repair/reconciliation tooling for drift.
- Keep the BFF path for the affected page as auth/signing plus one payload pass-through; remove response reshaping or aggregation that duplicates backend work.
- Parallelize independent SPA bootstrap requests with `Promise.all` or the equivalent query-cache orchestration.
- Add short-TTL client caching for current user, cycle list, and team list across navigation.
- Stream the authenticated page shell with Suspense so layout usability is independent from full snapshot completion.
- Establish budgets: usable shell under 1.5 seconds, authenticated page data under 3 seconds, and no avoidable sequential critical-path calls.
- Fix the dominant cause, then add a repeatable probe or regression test for the page-load budget.

Estimate: 20-32 hours / 3-5 sessions  
Dependencies: none  
Owner: frontend/backend/platform  
Risk: Critical

Definition of done:

- A trace identifies the dominant source of the 10-second load time with evidence.
- Snapshot versus fan-out behavior is confirmed for the affected page.
- Direct TCP, HTTPS fallback, semaphore wait, breaker/probe state, and cold-start effects are distinguishable in telemetry.
- The affected page meets the agreed load-time budget in warmed steady state, with cold-start behavior documented separately.
- Hierarchy query count is bounded as the number of Goal/Objective/KeyResult/Task nodes grows.
- Goal and Objective rollups are read from maintained values on the critical path, with reconciliation coverage.
- The BFF performs no page-specific aggregation or response transformation beyond its boundary responsibilities.
- Independent bootstrap work is parallelized, stable reference data is cached, and the shell is usable before the full data payload resolves.
- The performance probe is part of the production-readiness gate and fails on material regression.

This package must complete before P0-01. Tenant filters and RLS should not be
introduced while the system's request critical path is still unexplained.

### P0-01 - Tenant and membership domain model

Finding: No tenant identity, organization model, or membership model exists.

Root cause: The original deployment model assumed one organization per
instance, so authentication establishes a user but not a tenant context.

Tasks:

- Define tenant lifecycle states and membership roles.
- Define server-side tenant resolution for login, session, BFF, and backend requests.
- Decide how bootstrap administrators create the first tenant and membership.
- Define platform-owned versus tenant-owned records.
- Add domain errors for missing membership, suspended tenant, and ambiguous context.

Estimate: 12-18 hours / 2-3 sessions  
Dependencies: none  
Owner: backend/domain  
Risk: High

Definition of done:

- A request has one resolved tenant context or is rejected.
- Client payloads cannot select an unauthorized tenant.
- Tenant and membership lifecycle states are documented and tested.
- Authentication and session contracts expose the selected tenant only from server-validated membership.

### P0-02 - Tenant coverage inventory and legacy semantic classification

Finding: Cycles, teams, and users contain instance-wide or admin-owned
semantics that cannot safely receive a blind `tenant_id` column.

Root cause: “Global” behavior was valid in a single-organization deployment
but has no defined meaning in a multi-tenant system.

Tasks:

- Inventory every persisted entity, foreign key, uniqueness rule, index, retention rule, export, and job payload, starting with `AsyncJob`, `AuditEvent`, and `AuthThrottleState`.
- Classify each record as tenant-owned, platform-owned, or explicitly shared.
- Decide tenant ownership for users, teams, cycles, goals, objectives, key results, tasks, files, reports, and audit events.
- Identify legacy rows that require backfill, quarantine, or an explicit default tenant, including audit and job history.
- Produce a migration mapping and data-loss/rollback analysis.

Estimate: 16-24 hours / 3-4 sessions  
Dependencies: P0-01 domain vocabulary  
Owner: backend/data  
Risk: Critical

Definition of done:

- The inventory is complete and reviewed against models, migrations, routes, jobs, and exports.
- Cycles, teams, and users have explicit ownership semantics with no “global” ambiguity.
- Every legacy row has a deterministic migration disposition.
- The migration plan can be rehearsed and rolled back without deleting source data.

### P0-03 - Authorization and request-context enforcement

Finding: Existing authorization predicates do not yet include tenant
membership as a mandatory dimension.

Root cause: Authorization was designed for role and ownership within one
instance; tenant membership was not a possible policy input.

Tasks:

- Add a typed tenant context to request, service, and authorization boundaries.
- Make tenant membership a prerequisite to owner/manager/admin decisions.
- Reject client-supplied tenant identifiers that disagree with server context.
- Cover direct backend calls, BFF calls, admin routes, exports, and file access.
- Ensure authorization failures do not reveal another tenant’s existence.

Estimate: 16-24 hours / 3-4 sessions  
Dependencies: P0-01 and P0-02  
Owner: backend/security  
Risk: Critical

Definition of done:

- Every tenant-owned route requires resolved membership before data access.
- Existing role semantics remain correct within a tenant.
- Cross-tenant authorization denial is uniform and non-enumerating.
- The mutation authorization matrix includes tenant cases for every protected route.

### P0-04 - Database isolation and migration implementation

Finding: No tenant-specific schema boundary or RLS policy exists.

Root cause: The single-instance model did not require database-level tenant
predicates or tenant-scoped uniqueness.

Tasks:

- Define the RLS context contract and create two-tenant denial fixtures before feature migrations are implemented.
- Implement one request-scoped transaction helper that sets `SET LOCAL app.tenant_id` as the first statement and executes all following direct-Postgres queries inside that same transaction.
- Implement the approved tenant columns, foreign keys, indexes, and scoped uniqueness constraints.
- Add `USING (tenant_id = current_setting('app.tenant_id')::uuid)` policies, with explicit handling for missing context so the default is deny.
- Enable and `FORCE ROW LEVEL SECURITY` on every tenant-owned table.
- Verify the runtime database role does not have `BYPASSRLS` and is not an unrestricted owner role.
- Define safe migration ordering, backfill batches, verification queries, and rollback behavior.
- Ensure service roles and administrative tooling have explicit, audited bypass rules.
- Add database fixtures for at least two isolated tenants.

Estimate: 24-36 hours / 4-6 sessions  
Dependencies: P0-02 classification and tenancy ADR  
Owner: backend/data/operations  
Risk: Critical

Definition of done:

- Every tenant-owned table has an explicit RLS policy and a test proving a session cannot read or mutate another tenant's rows.
- A test omits `SET LOCAL app.tenant_id` and proves that RLS denies access rather than returning rows.
- A test proves transaction-local context cannot leak from one pooled transaction/request to another.
- Schema and RLS policies enforce the approved ownership model.
- Scoped uniqueness and foreign-key behavior are tested.
- Migration rehearsal succeeds on a representative legacy dataset.
- Rollback and partial-failure procedures are documented and exercised.

### P0-05 - Tenant propagation through async, exports, and audit

Finding: Tenant context is not yet a mandatory field across all asynchronous
and derived work paths.

Root cause: Tenant scope was not part of the original job, export, or audit
event contract.

Tasks:

- Add tenant context to job payload schemas and idempotency scope.
- Validate tenant context at enqueue, claim, retry, requeue, and execution boundaries.
- Scope exports, generated files, notifications, and audit events.
- Prevent dead-letter retry from changing tenant scope.
- Add redacted operator diagnostics that retain tenant correlation without exposing payload data.
- The Supabase HTTPS fallback is alpha/self-hosted compatibility only; multi-tenant SaaS uses direct Postgres through the approved pooler so RLS remains the authoritative database backstop.

Estimate: 16-24 hours / 3-4 sessions  
Dependencies: P0-01, P0-03, and existing job contracts  
Owner: backend/worker  
Risk: High

Definition of done:

- A job cannot execute without a valid tenant context.
- Retry and dead-letter flows preserve the original tenant and idempotency scope.
- Export/file access cannot cross tenant boundaries.
- Audit records identify tenant, actor, request, and job correlation safely.

### P0-06 - Cross-tenant denial and isolation regression suite

Finding: Existing authorization tests prove role behavior but do not prove
tenant isolation because no tenant fixture exists.

Root cause: The test model mirrors the single-instance domain.

This work starts before the corresponding feature implementation: each new
tenant-sensitive schema, route, export, and job path must receive a failing
denial test first, then its implementation, then the positive same-tenant test.

Tasks:

- Create two-tenant fixtures with overlapping user names, teams, cycles, and resource identifiers where possible.
- Extend the mutation-auth matrix for read, mutation, export, file, job, retry, and admin paths.
- Add direct backend, BFF, worker, and database/RLS denial tests.
- Add positive same-tenant tests so isolation work does not break valid workflows.
- Add contract tests for tenant fields and server-derived context.

Estimate: 20-30 hours / 3-5 sessions  
Dependencies: P0-01 through P0-05, incrementally testable  
Owner: quality/security  
Risk: Critical

Definition of done:

- Cross-tenant reads and writes are denied across every tenant-owned capability.
- Job, export, audit, and retry isolation are covered.
- Tests run deterministically in CI without shared mutable state.
- No critical or high isolation finding remains open.

### P0-07 - Tenancy ADR and operational exit review

Finding: Shared database versus database-per-tenant is high-impact and
hard-to-reverse, but must be decided with an explicit operating bias.

Root cause: Deployment topology was defined before tenant scale, residency,
and blast-radius requirements existed.

Tasks:

- Name an independent security reviewer before P0-04 begins; this must be a trusted outside engineer or peer who did not author the RLS policies and isolation tests.
- Start the ADR with shared PostgreSQL as the default for solo-maintainer and self-hosted practicality.
- Compare database-per-tenant against shared PostgreSQL for isolation, residency, noisy neighbors, backups, restore time, observability, cost, and maximum expected tenant count.
- Record the decision that HTTPS fallback is restricted to alpha and self-hosted deployments; reopening SaaS support requires a new threat model, API-filter parity suite, and explicit architecture approval.
- Record the conditions that would overturn the default.
- Review threat model, migration evidence, denial tests, SLO impact, and runbooks.

Estimate: 8-12 hours / 1-2 sessions  
Dependencies: P0-02 and P0-04 evidence  
Owner: architecture/security/operations  
Risk: High

Definition of done:

- ADR is approved and linked from the SaaS roadmap.
- ADR explicitly resolves direct-Postgres RLS context handling and HTTPS-fallback tenant enforcement.
- The reviewer identity, review date, evidence bundle, findings, and disposition are recorded before Phase 1 starts.
- Phase 0 exit review signs off on isolation invariants and unresolved risks.
- Phase 1 cannot start without the exit decision and evidence bundle.

## Sequence and capacity

Recommended order:

1. P0-00 performance trace, recovery, and load-time budget: first hierarchy eager-loading/N+1 fix, then write-time rollups.
2. P0-01 tenant and membership vocabulary.
3. P0-02 ownership inventory, with `AsyncJob`, `AuditEvent`, and `AuthThrottleState` first, then cycles, teams, and users.
4. P0-07 initial tenancy ADR once inventory constraints are known.
5. P0-06 create the two-tenant denial harness and first failing boundary tests.
6. P0-04 schema, RLS, and migration rehearsal, keeping denial tests ahead of each capability.
7. P0-03 request and authorization enforcement, aligned with the database boundary.
8. P0-05 async/export/audit propagation, beginning with `AsyncJob` and `AuditEvent`, each with a denial test before implementation.
9. P0-06 complete isolation regression suite and exit review.

Total planning range: 132-200 focused hours. At the stated capacity this is
approximately 8-17 calendar weeks, depending on migration complexity and review
availability. No Phase 1 cloud or regional work is committed before the exit
gate.

## Phase 0 exit gate

- Tenant identity is server-derived and mandatory.
- P0-00 has identified and addressed the dominant page-load bottleneck, with the load-time budget enforced.
- Ownership semantics for cycles, teams, users, and all persisted entities are approved.
- Schema migration, backfill, rollback, and RLS policies are rehearsed.
- Every tenant-owned table has an independently tested RLS backstop before tenant data is exposed.
- Cross-tenant denial tests pass at application, BFF, worker, and database boundaries.
- Jobs, retries, exports, files, and audit events preserve tenant context.
- OpenAPI and generated types reflect tenant-scoped contracts.
- Threat model has no open critical/high isolation findings.
- ADR, runbook, test evidence, and residual risks are recorded in the Phase 0 handoff.

## Tracking rules

- Update status in this document at the work-package level; do not recreate a second active ledger.
- Record implementation evidence, decisions, and incidents in `docs/WORKLOG.md` only after the fresh Phase 0 worklog is created.
- Reassess estimates after P0-02; do not silently carry uncertainty into P0-04.
- Any scope change affecting tenant isolation requires a new decision record and security review.

## Archived predecessor records

The previous architecture backlog, status ledger, and worklog are preserved in
the [architecture archive](../archive/architecture-2026-08-31/README.md).

