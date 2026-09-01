# Pre-SaaS Architecture Simplification Backlog

Documentation HQ: [README](README.md)

Status: ARCHIVED - COMPLETED HANDOFF  
Scope: historical record of architecture clarity, runtime canonicalization, and complexity control  
Position: completed prerequisite to `ENTERPRISE_SAAS_ROADMAP.md` Phase 0  
Planning horizon: 4-7 weeks at 12-16 focused hours per week  
Estimated effort: 52-92 focused hours  
Owner model: one primary maintainer, with an independent architecture reviewer at the exit gate

This document is no longer an executable backlog. The promoted mainline and
owner-approved single-tenant SaaS direction are now governed by
`ENTERPRISE_SAAS_ROADMAP.md` and
`docs/superpowers/specs/2026-09-01-single-tenant-saas-design.md`. The detailed
work packages below are retained as historical evidence of the pre-SaaS
initiative and must not be restarted without a new architecture decision.

## Delivery operating model

This backlog is executed through the Architecture Delivery System:
[ARCHITECTURE_DELIVERY_SYSTEM.md](docs/ARCHITECTURE_DELIVERY_SYSTEM.md).

Execution sources:

- Status ledger: [docs/architecture-status.md](docs/architecture-status.md)
- Working journal: [docs/WORKLOG.md](docs/WORKLOG.md)

All items must follow `PLANNED -> IN-PROGRESS -> IMPLEMENTED -> VERIFIED -> CLOSED`.
`CLOSED` requires the purpose-drill evidence and a one-line retrospective note.

## Tracking status snapshot

| Item | Lifecycle status | Evidence | Verified | Retro note |
|---|---|---|---|---|
| P0-00 | IN-PROGRESS | [docs/pre-saas-architecture-inventory.md](docs/pre-saas-architecture-inventory.md) | not yet | not yet |
| P0-01 | IN-PROGRESS | [docs/architecture-boundaries.md](docs/architecture-boundaries.md); canonical serializers, bucket, selector, bootstrap delegation, keyed/unkeyed snapshot-cache factories, all facade snapshot-cache wiring, and duplicate implementation removal completed; 29 combined boundary/cache tests passed; consolidated gate passed | partial | Snapshot behavior is verified; selector/bootstrap caller inventory, full boundary verification, and package closure remain. |
| P0-02 | IN-PROGRESS | [docs/runtime-entrypoint-contract.md](docs/runtime-entrypoint-contract.md); runtime matrix, compatibility readiness gate, isolated SaaS `database` readiness smoke, and live compatibility health payload passed | partial | SaaS API profile smoke verified; full SaaS topology and local/Kubernetes reconciliation remain. |
| P0-03 | IN-PROGRESS | [docs/bff-boundary-adr.md](docs/bff-boundary-adr.md); [docs/bff-security-review.md](docs/bff-security-review.md); allowlist passed for 44 routes; BFF suite passed 65 tests; consolidated gate passed | partial | Repository security controls reviewed; production secret, rate-limit, tenant-context, and rollback evidence remain. |
| P0-04 | IN-PROGRESS | [docs/compatibility-surface-cleanup.md](docs/compatibility-surface-cleanup.md); [docs/compatibility-callers.md](docs/compatibility-callers.md); [docs/launcher-command-matrix.md](docs/launcher-command-matrix.md); canonical cache migration, platform/login/response-scope migration, cycle/weekly-plan caller migration, explicit user serializer dependency seam, no-root-facade-import guard, and read-only Docker wrapper status path completed; 14 parity/ritual tests and 2 launcher contract tests passed; bounded Compose health captured | partial | Full wrapper start/stop rehearsal, launcher cleanup, and retirement of the parity override remain. |
| P0-05 | VERIFIED | [docs/documentation-lifecycle-control.md](docs/documentation-lifecycle-control.md); `python scripts/check_docs_hq_links.py` passed across 76 Markdown files after the signed-review regression repair | 2026-09-01 | Documentation control re-verified after REV-002; future ADRs must preserve the same ledger and link discipline. |
| P0-06 | IN-PROGRESS | [docs/governance-migration-exit-review.md](docs/governance-migration-exit-review.md); [docs/migration-rollback-runbook.md](docs/migration-rollback-runbook.md); migration safety register added; migration lint passed; bounded readiness gate passed; current image and Alembic baseline captured | partial | No-op downgrade is classified explicitly; migration and application rollback rehearsal remain. |

## Purpose

This backlog reduces structural ambiguity before multi-tenant SaaS work begins.
It is not a rewrite and it is not a cosmetic directory cleanup. The objective
is to make ownership, runtime boundaries, deployment paths, and documentation
unambiguous enough that new tenancy and RLS work does not multiply existing
complexity.

The current product has a strong OKR domain model and useful reliability
patterns, but its repository shape reflects an incremental migration: `src/`,
`backend_app/`, root entrypoints, `spa-bff/`, and `spa-web/` coexist. The BFF is
currently mostly pass-through. Several Windows launchers and multiple strategy
documents expose overlapping operational paths.

## Root-cause and system-thinking model

### Symptoms

- Contributors cannot immediately identify the canonical backend package or entrypoint.
- The BFF may be treated as either a required platform boundary or an unnecessary extra service.
- Local, alpha, self-hosted, and future SaaS startup paths can drift.
- Root scripts and compatibility entrypoints increase deployment and support surface.
- Architecture documents can describe plans that are no longer active.

### Structural causes

- Refactoring was performed incrementally without a final target topology and ownership matrix.
- Compatibility surfaces were retained without a lifecycle rule for removal or deprecation.
- Runtime responsibilities are distributed between facade modules, helpers, launchers, and deployment files.
- Documentation was allowed to accumulate instead of having one active execution backlog and explicit archives.
- Enterprise concerns were introduced before the product had a bounded architecture baseline.

### Failure modes if SaaS starts now

- Tenant context is implemented in one backend path while another entrypoint bypasses it.
- RLS, jobs, exports, or audit behavior is fixed in the canonical path but missed by a compatibility path.
- A BFF deployment decision is made under delivery pressure without evaluating security and operational tradeoffs.
- A cleanup rewrite changes domain behavior while appearing to be structural-only.
- Operators use different commands for environments and cannot reproduce a production incident locally.

### Desired system behavior

- One canonical backend package and one canonical backend startup contract.
- Every alternate entrypoint is either a thin compatibility wrapper with an owner and removal condition or is removed.
- The BFF has an explicit responsibility contract and a documented keep/remove decision.
- Local, alpha, self-hosted, and SaaS profiles select documented capabilities without hidden mode changes.
- Active architecture guidance has one source of truth; historical material is archived and clearly labeled.
- New SaaS controls are added to stable seams rather than to migration leftovers.

## Non-negotiable constraints

- Do not rewrite domain behavior, authorization rules, persistence semantics, or API contracts as part of structural cleanup.
- Do not merge modules solely to reduce directory count.
- Do not remove the BFF or compatibility launchers before usage, security, and rollback evidence exists.
- Do not begin tenant schema or RLS implementation until the canonical runtime path is approved.
- Preserve OpenAPI output, generated client types, mutation allowlists, and existing quality gates.
- Preserve supported self-hosted and alpha behavior unless a separate deprecation decision is approved.
- Every relocation or deletion must have an import, startup, contract, and rollback plan.

## Target architecture decision to implement

The default target is a modular monolith backend plus independently deployable
SPA. The backend keeps explicit internal package boundaries for API adapters,
domain logic, persistence/read queries, workers, configuration, and bootstrap.

The default BFF decision is **defer separate deployment unless a concrete
responsibility justifies it**. Candidate responsibilities that can justify it
are secure browser session handling, a deliberate public/private network
boundary, frontend-specific composition across independent services, edge rate
limiting, or a separately scaled browser-facing tier. Pass-through proxying
alone is not sufficient justification.

This is a starting bias, not permission for immediate removal. The decision is
recorded through P0-03 and must include security, latency, deployment, rollback,
and future multi-tenant implications.

## Work packages

### P0-00 - Architecture inventory and target topology

Finding: The repository contains multiple runtime and package surfaces whose
ownership is not obvious from the root.

Root cause: Incremental extraction created seams without a final ownership map.

Tasks:

- Inventory Python packages, root entrypoints, BFF entrypoints, SPA entrypoints, workers, migrations, Docker services, and launch scripts.
- Trace startup from each supported command to the actual application factory.
- Identify imports that cross domain, API, persistence, worker, and UI boundaries.
- Classify every surface as canonical, compatibility, test-only, or removable.
- Produce a target topology diagram and ownership matrix.
- Record behavior that must remain unchanged during structural work.

Estimate: 8-12 hours / 1-2 sessions  
Dependencies: none  
Owner: architecture  
Risk: Medium

Definition of done:

- Every runtime surface has one owner and one lifecycle classification.
- One canonical backend startup path is named.
- Target package boundaries and forbidden dependency directions are documented.
- No cleanup task begins without a mapping from old surface to target surface.

### P0-01 - Canonical backend package and facade boundary

Finding: `src/` and `backend_app/` both appear to be backend roots, while
facades and helper modules distribute public ownership.

Root cause: Extraction reduced file size but did not finish package ownership.

Tasks:

- Choose the canonical backend package name and import boundary.
- Keep `backend_app.main` as a compatibility facade only where external imports require it.
- Define package ownership for HTTP routes, domain services, read queries, persistence, jobs, and bootstrap.
- Move implementation modules incrementally behind those boundaries without changing behavior.
- Add import-direction checks that prevent domain code from importing HTTP or deployment code.
- Add a deprecation/removal record for every compatibility alias.
- Keep module design and helper-integrity gates green after each slice.

Estimate: 16-28 hours / 2-4 sessions  
Dependencies: P0-00  
Owner: backend  
Risk: High

Definition of done:

- A new contributor can locate each backend responsibility from the target map.
- The canonical application factory is used by local, container, and test startup.
- Facades contain delegation and public compatibility exports, not business logic.
- Import-direction and module-design checks enforce the target boundary.
- No public API or persisted-data behavior changes without a separate change record.

### P0-02 - Runtime and deployment entrypoint canonicalization

Finding: Root scripts and environment-specific launchers can create multiple
ways to start substantially similar runtimes.

Root cause: Compatibility and alpha constraints were encoded as scripts instead
of a single profile-driven startup contract.

Tasks:

- Define canonical commands for development, test, alpha/self-hosted, and SaaS.
- Make Docker Compose and `just` or equivalent automation call the same underlying commands.
- Convert root `.bat` files into thin compatibility wrappers or move their implementation into `scripts/`.
- Document the owner, supported environment, and removal condition for each wrapper.
- Ensure SaaS profile rejects unsupported HTTPS fallback rather than silently promoting to it.
- Add startup checks that report the selected deployment profile and data-access mode.
- Confirm worker and API use compatible configuration semantics.

Estimate: 10-18 hours / 2-3 sessions  
Dependencies: P0-00  
Owner: platform  
Risk: High

Definition of done:

- Each supported environment has one documented canonical startup command.
- Compatibility scripts contain no independent business or deployment logic.
- Backend, worker, and frontend profile selection is observable and consistent.
- SaaS cannot start with an unsupported data-access mode.
- A rollback command exists for every entrypoint migration.

### P0-03 - BFF responsibility and topology ADR

Finding: `spa-bff` currently adds a service boundary while performing little or
no response transformation for the main page path.

Root cause: The BFF was introduced as a useful boundary, but its long-term
responsibility was not separated from its current proxy implementation.

Tasks:

- Measure BFF latency, failure modes, connection behavior, and operational cost.
- Document current responsibilities: authentication, signing, cookie handling, routing, rate limiting, and proxying.
- Compare three options: retain separate BFF, embed the boundary in the backend, or replace it with an edge/API gateway.
- Evaluate browser security, tenant context, observability, scaling, incident isolation, and rollback for each option.
- Choose a default and record conditions that would reverse it.
- If retained, define a responsibility test that prevents accidental page-specific business logic.
- If removed, create a staged migration with dual-run, rollback, and security parity evidence.

Estimate: 8-16 hours / 1-3 sessions  
Dependencies: P0-00 and measured performance trace  
Owner: architecture/security/platform  
Risk: Critical

Definition of done:

- ADR-002 records the BFF decision and reviewer approval.
- The chosen topology has explicit network, authentication, tenant-context, and observability boundaries.
- The BFF either has justified responsibilities or has an approved removal plan.
- No tenant/RLS work depends on an unresolved BFF boundary.

### P0-04 - Root script and compatibility surface cleanup

Finding: Root-level Windows scripts and duplicate entrypoints create support
and discoverability cost.

Root cause: Historical launch paths were retained without consolidation.

Tasks:

- Inventory usage of `*.bat`, root `app.py`, legacy launchers, and compatibility imports.
- Move implementation into platform-neutral scripts or task recipes.
- Retain only explicitly supported compatibility wrappers at the root.
- Add deprecation messages and documentation links before removing any wrapper.
- Update CI, Docker, deployment runbooks, and contributor documentation.
- Verify paths on Windows and Linux where both are supported.

Estimate: 6-10 hours / 1-2 sessions  
Dependencies: P0-01 and P0-02  
Owner: platform  
Risk: Medium

Definition of done:

- Root entrypoints are limited to canonical files and documented compatibility wrappers.
- No script contains a second implementation of startup or deployment policy.
- CI and runbooks use canonical commands.
- Removal of obsolete wrappers is reversible for one release cycle.

### P0-05 - Documentation consolidation and lifecycle control

Finding: Roadmaps and architecture documents can compete to describe current
work, creating specification drift.

Root cause: Planning, evidence, decisions, and historical records were not
separated strongly enough.

Tasks:

- Make this document the active pre-SaaS simplification backlog.
- Keep `ARCHITECTURE_BACKLOG.md` focused on the later tenant foundation.
- Keep `ENTERPRISE_SAAS_ROADMAP.md` focused on product phases and promotion gates.
- Move superseded plans to the archive with a clear redirect.
- Ensure each active document has a Documentation HQ backlink.
- Add document owner, status, review trigger, and source-of-truth labels.
- Remove duplicate implementation instructions from roadmaps and place them in runbooks or ADRs.
- Update English/Persian mirrors when the changed guidance is operational.

Estimate: 6-10 hours / 1-2 sessions  
Dependencies: P0-00  
Owner: architecture/documentation  
Risk: Low

Definition of done:

- One active source exists for each architecture, backlog, strategy, and operational concern.
- Historical documents cannot be mistaken for current instructions.
- Documentation link and lifecycle checks pass.
- A future document has a defined admission and archival rule.

### P0-06 - Governance, migration safety, and exit review

Finding: Structural changes can appear low-risk while silently changing imports,
startup behavior, or deployment assumptions.

Root cause: Architecture cleanup lacks a standard evidence bundle and promotion
gate.

Tasks:

- Define a change checklist for imports, startup, API contracts, migrations, workers, and deployment.
- Require focused tests and quality gates for each relocation or deletion.
- Capture before/after startup topology and dependency evidence.
- Record rollback steps and a release boundary for each migration slice.
- Have an independent reviewer inspect P0-01 through P0-05 evidence.
- Record residual complexity and explicit deferred work before SaaS Phase 0 begins.

Estimate: 4-8 hours / 1 session  
Dependencies: P0-01 through P0-05  
Owner: architecture/reviewer  
Risk: High

Definition of done:

- The evidence bundle is reviewed by a named independent reviewer.
- Canonical startup works in supported environments.
- Contract, integrity, module-design, and documentation gates pass.
- Rollback procedures are documented and rehearsed for high-risk changes.
- SaaS Phase 0 promotion is explicitly approved.

## Sequence and capacity

Recommended order:

1. P0-00 inventory and target topology.
2. P0-03 BFF decision in parallel with the performance trace, without changing topology yet.
3. P0-01 canonical backend boundaries.
4. P0-02 runtime and deployment entrypoints.
5. P0-04 root script and compatibility cleanup.
6. P0-05 documentation consolidation.
7. P0-06 independent exit review.

Total estimate: 52-92 focused hours. At 12-16 focused hours per week, this is
approximately 4-7 calendar weeks. The upper bound includes one correction loop
for boundary regressions and reviewer findings.

## Delivery-system mapping for this backlog

Each item must produce:

- A `PLANNED`-to-`IN-PROGRESS` move in `docs/architecture-status.md` before work starts.
- An `IMPLEMENTED` entry with PR/commit and test evidence.
- A verification drill result matching the item objective.
- A `CLOSED` entry with a one-line retrospective note.

Target verification alignment:

- P0-00: Topology evidence drill (ownership map + startup flow capture).
- P0-01: Ownership boundary drill (import direction and facade call-path verification).
- P0-02: Startup profile drill (canonical command and profile enforcement check).
- P0-03: BFF decision drill (option comparison and chosen-boundary evidence).
- P0-04: Script cleanup drill (compatibility surface inventory and usage check).
- P0-05: Documentation consolidation drill (single-source-of-truth and archive-rule check).
- P0-06: Governance and migration drill (rollback proof + independent exit review).

## Promotion gate to SaaS Phase 0

SaaS Phase 0 cannot start until all of the following are true:

- The target topology and backend ownership matrix are approved.
- One canonical backend startup path is used by supported environments.
- Compatibility entrypoints have owners, deprecation conditions, and rollback paths.
- The BFF keep/remove decision is recorded and its tenant-context boundary is explicit.
- SaaS profile configuration cannot select alpha/self-hosted HTTPS fallback.
- Active architecture and roadmap documents have one source of truth each.
- Performance tracing identifies the remaining critical path, with known completed fixes separated from unresolved work.
- Module-design, helper-integrity, contract, and documentation gates pass.
- A named independent reviewer approves the evidence bundle.
- No structural migration has an undocumented behavior or rollback risk.

## Explicitly deferred

- Microservice extraction.
- Turborepo/Nx adoption.
- Database-per-tenant implementation.
- Regional deployment and data residency.
- Removing the BFF without an approved ADR and security parity evidence.
- Broad rewrite of `src/` or `backend_app/` solely for naming consistency.

## Relationship to SaaS planning

This backlog is the prerequisite architecture simplification phase. After its
promotion gate, execution continues in:

- [Enterprise SaaS Roadmap](ENTERPRISE_SAAS_ROADMAP.md)
- [Phase 0 Multi-Tenant Backlog](ARCHITECTURE_BACKLOG.md)

The tenant backlog remains the authority for tenant identity, ownership,
authorization, RLS, jobs, exports, and audit isolation. This document must not
duplicate those implementation tasks.
## Signed review follow-up: 2026-09-01

P0-06 remains `IN-PROGRESS`. The actual runtime compatibility database is at `drop_global_cycle_index (head)`. A PostgreSQL 17-compatible backup of the live runtime database was successfully restored into an isolated rehearsal instance, with no live data change. The remaining condition is an application release rollback rehearsal using a prior deployable artifact before tenant/RLS schema work begins.
## Owner decision: disposable pre-SaaS database - 2026-09-01

The owner explicitly chose a disposable pre-SaaS database posture. All application tables in the runtime database were purged with cascading truncation; the schema was retained and no migration or database dump is required for this phase. P0-06 is therefore re-scoped: database backup/recovery and Alembic reconciliation are out of scope until the SaaS persistence phase, while application rollback documentation remains the only relevant rollback follow-up.
## Owner confirmation: branch promotion - 2026-09-01

The owner confirmed that the reviewed `SPA-BFF-clean` work was promoted to the project mainline. The signed-review scope-integrity condition is resolved for this review. The pre-SaaS baseline is now the promoted branch with an intentionally empty runtime database; tenant/RLS and SaaS persistence work remain deferred.
## Active handoff: pre-SaaS product baseline

The promoted mainline and empty runtime database are the working baseline. Proceed with pre-SaaS product implementation and integration work without introducing tenant identifiers, RLS policies, tenant-scoped migrations, or SaaS persistence commitments. Reopen the deferred SaaS persistence controls only when real persistent data or a tenant boundary is intentionally scheduled.
## Decision: architecture initiative handoff - 2026-09-01

The pre-SaaS architecture initiative is handed off to product implementation. No additional architecture backlog items should be invented at this stage. New work should be added only when it has a concrete product requirement, an identified production risk, or an intentional transition into SaaS persistence and tenant isolation.

Handoff baseline:

- Promoted mainline contains the reviewed architecture work.
- Runtime application data is empty and disposable.
- Schema is retained for the running services.
- Automated architectural gates were previously re-run successfully.
- Tenant/RLS, durable SaaS persistence, and database recovery controls are deferred by decision.
## P0-06 disposition: deferred by explicit owner risk acceptance - 2026-09-01

The owner explicitly accepts the risk of not rehearsing production-grade application/database rollback during disposable pre-SaaS work. P0-06 is deferred, not technically verified or deleted. Before production SaaS persistence or tenant/RLS work begins, the project must restore the backup/recovery mechanism as a hard gate with a provider-supported backup, isolated restore test, application release rollback rehearsal, documented RPO/RTO, and named operational owner.

## Archive precedence

The active execution source is now `ENTERPRISE_SAAS_ROADMAP.md`. The approved single-tenant model supersedes the older shared-database/RLS starting bias in the historical work packages above. Do not restart this backlog or introduce tenant/RLS schema work until the active roadmap schedules that transition.
