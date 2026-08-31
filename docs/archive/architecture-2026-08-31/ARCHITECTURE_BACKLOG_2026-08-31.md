# Architecture Backlog — Production Hardening (Revised + Enriched)

Documentation HQ: [README](../../../README.md)

**Execution tracking**: progress against this backlog is tracked in
[docs/architecture-status.md](docs/architecture-status.md) (status ledger +
verification drills) and [docs/ARCHITECTURE_DELIVERY_SYSTEM.md](docs/ARCHITECTURE_DELIVERY_SYSTEM.md)
(process definition). Session journal: `docs/WORKLOG.md`.

> **Revision note (2026-08-24):** This backlog was re-assessed against the
> actual codebase. Several original findings were stale or incorrect and have
> been removed; remaining items are scoped to verified gaps only. See
> [Removed items](#removed-items-were-stale-or-incorrect) at the end.
>
> **Revision note (2026-08-25):** All four original P0 items are IMPLEMENTED
> (see status ledger). New P0 items added from the enterprise-roadmap review:
> finish sprint loose ends (SLO probe coverage, generated-type adoption,
> allowlist generation). Multi-tenant work explicitly deferred as greenfield.
>
> **Revision note (2026-08-26):** Approved new feature — per-manager active
> cycles with a manager-accessible Cycles panel. Plan:
> [docs/PLAN_PER_MANAGER_ACTIVE_CYCLES.md](docs/PLAN_PER_MANAGER_ACTIVE_CYCLES.md).
> Design decisions: legacy unowned cycles backfilled to admin ownership;
> admin-owned active cycles visible to everyone; managers get the Cycles panel
> only; teams handling deferred (membership stays a data field).
>
> **Revision note (2026-08-26, later):** The four legacy verification drills and
> the per-manager Phase E3 drill were completed and recorded in the status
> ledger. Items 1 through 6 are now CLOSED. The next active work is the P1
> data-access strategy hardening stage.

> **Revision note (2026-08-31):** The enterprise architecture review identified
> maintainability improvements that are real but not production blockers. They
> are tracked below as P2 work; no broad repository rewrite is approved.

## 1) Context and operating assumptions

This is a single-maintainer production plan for an enterprise OKR app. The
current validation environment is a local workstation with Supabase free tier
and Docker Compose. The objective is to improve reliability and operations
without unnecessary architecture churn.

Assumptions:
1. No external platform migration in the next quarter.
2. Existing CI/CD pipeline remains the change gate.
3. Security posture must stay backward compatible for at least one release.
4. `spa-web`, `spa-bff`, and `backend_app` remain the deployed runtime stack.

Execution constraints:
1. Favor low-risk, reversible changes first.
2. Keep data model/API shape changes backward compatible when possible.
3. Preserve local/dev workflows that depend on current test and boot scripts.

## 2) Backlog enrichment model

For each item, we track:
1. **Root-cause trace**: why this exists and what changed to create the gap.
1. **Systems impact**: blast radius across API, frontend, BFF, background jobs.
1. **Work decomposition**: implementation steps grouped by layer.
1. **Owners and timebox**: practical execution planning.
1. **Definition of done**: objective completion check.
1. **Regression control**: what to validate immediately after change.

## P0 — Essential for production

### 0) Finish sprint loose ends (NEW — top priority)

**Finding**: The reliability sprint left three loose ends that reduce the value
of what was built:
1. `scripts/slo_probe.py` implements only SLO-1 (login p95) + healthz check;
   SLO-2–5 (read p95, mutation error rate, job queue lag, snapshot latency)
   are defined in the runbooks doc but not measured.
2. Generated OpenAPI types (`spa-web/src/lib/api/generated/schema.d.ts`) are
   imported only by the `backend-schema.ts` helper — no app code uses them yet.
3. The four original backlog items below were IMPLEMENTED and are now CLOSED;
   their live verification drills are recorded in the status ledger.

**Work decomposition**:
1. Extend `scripts/slo_probe.py`: add read/query p95, mutation error rate,
   job queue lag, and snapshot latency probes matching the runbook SLO table.
2. Migrate `/v1/read/query` payload handling to generated types using the
   `backend-schema.ts` pattern; then batch remaining endpoints.
3. Preserve the recorded verification evidence in the ledger and keep the
   recurring operational drills on their documented cadence.

**Definition of done**:
1. Probe measures all 5 SLOs with pass/fail exit codes.
2. No hand-written response types remain on read paths in app code.
3. All four original ledger items CLOSED with dated drill evidence. **Complete
   as of 2026-08-26.**

**Estimate**: 3–5 focused sessions.

### 1) Typed API contracts / OpenAPI codegen

**Finding**: `spa-web/src/lib/api/types.ts` currently hand-defines response types
while route templates in `spa-bff/src/allowlist.ts` are manually maintained. Mutation
contract checks exist, but read payload drift is still possible.

> Note: reads flow through the single `/v1/read/query` endpoint with a `kind`
> discriminator (e.g. `krs.by_cycle`, `ritual.snapshot`) — there is no per-entity
> REST read path, so codegen adoption targets response payload types per kind.

**Root-cause trace**: Build-time contract enforcement exists for selected paths,
but not for all payload read paths. Manual typing and manual allowlist maintenance
create asymmetric change pressure on frontend and BFF.

**Systems impact**: Silent runtime mismatch risk during frontend release can
manifest as broken dashboards, failed queries, and degraded fallback handling.

**Work decomposition**:
1. Backend: export OpenAPI from FastAPI in CI as a versioned artifact.
1. Frontend toolchain: generate types (e.g. `openapi-typescript`) into
   `spa-web/src/lib/api/generated`.
1. Consumption: migrate `/v1/read/query` first, then batch additional endpoints.
1. Guardrail: add a drift job to fail CI if committed generated file changes.

**Owner / effort / sequencing**:
1. Owner: Backend + frontend (pair).
1. Estimate: 10–16 hours.
1. Dependency: stable OpenAPI output and deterministic codegen in CI container.

**Definition of done**:
1. Backend API change that changes payload shape fails the frontend type gate.
1. Type drift is surfaced as a CI failure with an actionable artifact diff.
1. Initial two read kinds (`krs.by_cycle`, `ritual.snapshot`) moved to generated
   types with no manual overrides.

**Status update (2026-08-31)**: Infrastructure and the first app-code adoption
slice are complete — Atlas snapshot and discriminator-based read-query request
bodies now use generated OpenAPI contracts. The common read-query response
envelope now publishes typed sections for the ritual and KR workflows while
preserving unknown fields; timeline task/work-log and shared resource sections
are now typed as well. BFF allowlist generation is tracked separately as item
5.

**Regression control**:
1. Run existing mutation matrix tests to confirm endpoint gating remains valid.
1. Smoke test end-to-end query/read paths through BFF.

### 2) Signing key rotation playbook

**Finding**: The canonical signing payload is shared via `src/utils/crypto_utils.py`,
consumed by both `spa-bff/src/signing.ts` and `backend_app/security.py`. Rotate-ready
controls for active keys are missing.

**Root-cause trace**: Security model assumed static key operation; production
operations now need non-downtime operations, which are not represented in current
environment variables or runbooks.

**Systems impact**: Key replacement currently risks downtime or deploy-coupled
change windows, increasing operational risk.

**Work decomposition**:
1. Auth contract: add optional `x-okr-key-id` and strict unknown-ID rejection.
1. Verification path: support current + previous key for overlap window only.
1. Operations: document runbook in `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`
   (generate, verify-only deploy, cutover, retire).
1. Controls: add tests for overlap acceptance and unknown ID rejection.

**Owner / effort / sequencing**:
1. Owner: Security/platform.
1. Estimate: 6–10 hours.
1. Dependency: current config loading and secret management flow.

**Definition of done**:
1. Rotate keys via environment/config only, without application code changes.
1. No rejected valid traffic during defined overlap window.
1. Unknown key IDs return explicit authorization error.

**Regression control**:
1. Run signing tests in both BFF and backend integration paths.
1. Verify both old and new keys authenticate during overlap in staging-like local run.

### 3) Formal SLO definitions

**Finding**: Observability and request-id continuity are already present (`test_backend_observability.py`),
but formal targets and budgets are not defined in runbooks.

**Root-cause trace**: Signals were monitored operationally but not converted to
service-level objectives with ownership and thresholds.

**Systems impact**: Without explicit SLOs, incident triage and prioritization is
reactive rather than objective-driven.

**Work decomposition**:
1. Set target metrics for: login p95, read/query p95, mutation error rate,
   job queue lag, check-in snapshot latency.
1. Record thresholds and burn-rate policy in
   `docs/OBSERVABILITY_AND_RUNBOOKS.md`.
1. Extend `scripts/perf_hotpaths.py` to produce periodic SLO checks.

**Owner / effort / sequencing**:
1. Owner: Platform + product.
1. Estimate: 6–12 hours.
1. Dependency: stable metrics emission from current stack.

**Definition of done**:
1. Each metric has target, current baseline, and alert trigger.
1. One operator can measure all SLOs from documented command set.
1. Runbook includes immediate corrective actions per breached threshold.

**Regression control**:
1. Validate script runs in under 5 minutes with clear exit condition.
1. Threshold-breach behavior verified by documented manual check (unit-tested
   threshold logic; live breach simulation impractical at this deployment scale).

### 4) Dead-letter visibility for async jobs

**Finding**: Job system already includes idempotency keys, unique index
(`n4b5c6d7e8f9`), retry classification, and stale RUNNING reaping. Missing
observability for exhausted jobs requires manual SQL.

**Root-cause trace**: Pipeline resiliency was implemented first, but operator UX
for terminal failures was deferred.

**Systems impact**: Operational recovery is slower and less reliable without
first-party access to failed/poisoned jobs.

**Work decomposition**:
1. Add admin endpoint `GET /v1/jobs/dead` for `FAILED` + terminal attempt limit jobs.
1. Add `POST /v1/jobs/{id}/retry` to reset attempts for transient failure cases.
1. Add dead-job count into `/healthz` payload for monitoring.

**Owner / effort / sequencing**:
1. Owner: Backend + reliability.
1. Estimate: 8–12 hours.
1. Dependency: existing admin auth and job table schema.

**Definition of done**:
1. Operator can identify terminal failed jobs via API.
1. Operator can re-run a transient-failed job without SQL access.
1. Healthz report includes dead-job count and trend.

**Regression control**:
1. Add tests for dead endpoint filtering and retry permission checks.
1. Ensure non-admin users receive denied responses on new endpoints.

### 5) Generate BFF allowlist from contract metadata (NEW)

**Finding**: `spa-bff/src/allowlist.ts` is a hand-maintained literal array of
path templates + regexes. Sync is CI-enforced via the auth-matrix test (which
caught a real miss during the sprint), but every new route requires manual
edits in two places plus the test matrix.

**Root-cause trace**: Route policy predates the OpenAPI artifact; generation
was deferred until the schema export existed (it now does).

**Systems impact**: Manual allowlist maintenance is a recurring friction point
and a future drift risk if the matrix test is ever weakened.

**Work decomposition**:
1. Emit route metadata (method, path template, auth class) from the FastAPI
   schema into a JSON policy file alongside `openapi.json`.
2. Generate `spa-bff/src/allowlist.ts` from that policy file (build script).
3. Keep the auth-matrix test as the independent verifier of the generated file.

**Definition of done**:
1. Adding a backend route updates the allowlist via regeneration, not hand edit.
2. Auth-matrix test still passes unchanged (it verifies semantics, not text).
3. CI drift gate covers the generated allowlist.

**Status update (2026-08-26)**: CLOSED. `scripts/generate_bff_allowlist.py`
validates the explicit `spa-bff/src/route-policy.json` against the committed
OpenAPI artifact and generates `spa-bff/src/allowlist.ts`. CI and package drift
checks are wired, and the generator regression tests plus unchanged BFF
auth-matrix pass.

**Estimate**: 4–8 hours.

### 6) Cycle lifecycle hardening (NEW — 2026-08-25)

**Finding**: The single-active-cycle invariant was enforced only at the
application layer (bulk-deactivate before activate in ORM and Supabase-API
paths). Review of the cycle handling mechanisms surfaced six additional gaps:
1. No DB-level enforcement — two concurrent activations can both succeed.
2. Supabase REST activation is non-transactional (deactivate + activate are
   separate HTTP calls; a failure between them leaves zero active cycles).
3. Deactivating the last active cycle is allowed silently, leaving the
   workspace without a cycle.
4. `app.py`'s process-local `_cached_get_all_cycles` never consumes
   distributed invalidation broadcasts (`check_distributed_cache_staleness`
   has no caller), so multi-node deployments can serve stale cycles.
5. Admins/managers can deep-link to inactive cycles with no visual cue that
   they are viewing a non-current period.
6. Cycles are fetched independently by `useAdminResources` and
   `refreshSessionCycles`, risking drift between admin panel and top bar.

**Root-cause trace**: Cycle activation predates the concurrency/ops review;
the invariant lived in code paths rather than schema, cache, or UI contracts.

**Systems impact**: Wrong-period OKR data displayed workspace-wide (observed
in production use); potential zero-active-cycle states after partial failures;
stale dropdowns on multi-node deployments.

**Work decomposition**:
1. DB: Alembic migration adding partial unique index `ux_cycle_single_active`
   on `cycle(is_active) WHERE is_active`; mirror in `src/models.py`.
2. Backend: atomic activation via Postgres RPC (Supabase path) with
   application-level fallback; guard against deactivating the last active
   cycle at service layer.
3. Cache: wire `check_distributed_cache_staleness()` into the request path.
4. Frontend: read-only active-cycle display (done), inactive-cycle banner,
   consolidated cycles store hook.
5. Tests: concurrent-activation race, supabase mid-failure, UI read-only.

**Definition of done**:
1. Second concurrent activation fails with IntegrityError (DB-enforced).
2. Supabase-path failure cannot leave zero active cycles.
3. UI prevents last-cycle deactivation without explicit confirmation.
4. Multi-node cache staleness consumed per request.
5. All new tests green; full suites pass.

**Estimate**: 6–10 focused sessions.

## P1 — Data access strategy hardening

The next stage makes the existing TCP-primary/HTTPS-fallback behavior explicit
at the application boundary without changing its current production semantics.
These items are intentionally sequenced: define the contract first, then move
selection and telemetry behind it, and finally prove outage behavior.

### 7) Define the data-access strategy contract

**Finding**: Read and mutation dispatch currently relies on mode strings,
module-level helpers, and compatibility paths rather than one explicit
application-facing contract.

**Root-cause trace**: TCP-primary/HTTPS-fallback support was added incrementally
to preserve deployment compatibility, so strategy selection remains coupled to
global configuration and fallback state.

**Systems impact**: New access modes or callers can accidentally bypass common
timeouts, circuit-breaking, mutation fail-closed rules, or fallback telemetry.

**Work decomposition**:
1. Define a minimal `IDataAccessStrategy` protocol for the existing read,
   mutation, and RPC operations.
2. Define typed result/error metadata for selected strategy and fallback reason.
3. Add adapters for the current direct-DB and Supabase API implementations.
4. Keep existing public helper signatures as compatibility wrappers during the
   migration.

**Owner / effort / sequencing**:
1. Owner: Backend/platform.
2. Estimate: 1–2 focused sessions.
3. Dependency: current resolver and Supabase operation helpers.

**Definition of done**:
1. New application code can depend on the protocol without importing mode
   globals or concrete transport helpers.
2. Direct-DB and Supabase API paths satisfy the same contract tests.
3. No production behavior changes are introduced by the interface alone.

**Regression control**:
1. Run existing dual-mode parity, mutation fail-closed, and circuit-breaker
   tests against both adapters.
2. Run the full backend test suite before moving to item 8.

### 8) Make strategy selection request-scoped

**Finding**: Runtime strategy decisions and fallback latches are partly held in
   module-level mutable state, which is difficult to reason about across
   concurrent requests or multiple workers.

**Root-cause trace**: The resolver was designed around a single-process
   deployment envelope and later gained lifecycle controls without a complete
   request-scoped selection boundary.

**Systems impact**: One request’s fallback or recovery state can influence
   another request, producing inconsistent routing and harder incident analysis.

**Work decomposition**:
1. Introduce a request-scoped access context containing actor/request IDs,
   preferred strategy, and fallback policy.
2. Move strategy selection behind a resolver/service that receives this context.
3. Bound fallback state by process/instance health only where necessary, and
   make that distinction explicit from request-local state.
4. Preserve fail-closed mutation behavior during fallback and outage recovery.

**Owner / effort / sequencing**:
1. Owner: Backend/platform.
2. Estimate: 2–3 focused sessions.
3. Dependency: item 7 contract and existing resolver tests.

**Definition of done**:
1. Request routing does not read or mutate a mode global directly.
2. Concurrent requests with different contexts remain isolated.
3. Read fallback and mutation refusal behavior remain backward compatible.

**Regression control**:
1. Add concurrent request isolation tests.
2. Exercise TCP failure, HTTPS fallback, recovery, and mutation fail-closed
   paths with independent request contexts.

### 9) Add strategy and fallback observability

**Finding**: Existing logs and metrics show request outcomes, but do not
   consistently attribute the selected data-access strategy or fallback reason.

**Root-cause trace**: Observability was added around transport failures before
   the access strategy became a first-class application concept.

**Systems impact**: Operators can see that a request failed or was slow, but
   cannot reliably determine whether direct DB, Supabase API, or fallback logic
   caused the result.

**Work decomposition**:
1. Emit structured fields for strategy, fallback reason, resolver state, and
   duration at the request boundary.
2. Add counters and latency histograms partitioned by strategy and outcome.
3. Redact credentials, payloads, and sensitive actor data from telemetry.
4. Document dashboard queries and expected cardinality limits.

**Owner / effort / sequencing**:
1. Owner: Backend/operations.
2. Estimate: 1–2 focused sessions.
3. Dependency: item 8 request-scoped selection.

**Definition of done**:
1. Any sampled request can be explained by strategy and fallback reason.
2. Metrics distinguish normal fallback from outage, timeout, and policy refusal.
3. Telemetry remains bounded and contains no secrets or request bodies.

**Regression control**:
1. Add structured-log and metric assertions for normal, fallback, and refused
   mutation paths.
2. Run the SLO probe and confirm existing thresholds remain interpretable.

### 10) Verify failure-mode and recovery behavior

**Finding**: The current fallback behavior is tested, but the new strategy
   boundary needs an explicit operational drill proving isolation and recovery.

**Root-cause trace**: Existing tests validate individual controls; they do not
   yet verify the complete request-scoped strategy lifecycle under concurrent
   failure and recovery.

**Systems impact**: A refactor could preserve unit-level behavior while
   introducing cross-request leakage, fallback loops, or unsafe mutations during
   an outage.

**Work decomposition**:
1. Add deterministic fault injection for direct-DB timeout/unavailability.
2. Verify reads fall back within bounded latency and mutations fail closed.
3. Verify recovery returns traffic to the preferred strategy without stale
   request state.
4. Capture drill output and update the status ledger and runbook.

**Owner / effort / sequencing**:
1. Owner: Backend/reliability.
2. Estimate: 1–2 focused sessions.
3. Dependency: items 7–9.

**Definition of done**:
1. Concurrent requests remain isolated during induced primary failure.
2. No mutation is sent through an unauthorized or unhealthy fallback path.
3. Recovery and telemetry evidence are documented and repeatable.

**Regression control**:
1. Run focused fault-injection tests, then the full backend and deployment
   smoke suites.
2. Do not close the stage until the drill evidence is recorded.

## P2 — Deferred (real but not blocking production)

| Item | Gap | Why deferred | Trigger condition to promote |
|---|---|---|---|
| Monorepo & Package Management Tooling | Ad-hoc directory layout across Python and JavaScript services | Root workspace manifests now establish dependency boundaries; incremental build caching remains deferred until service growth justifies it | Dependency conflicts, service growth, or a need for incremental builds/caching |
| Workspace lockfiles | Lockfile compatibility with every external deployment environment is not yet confirmed | Root lockfiles are generated and consumed by CI and the Docker runtime; external deployment consumers remain to be reviewed | Dependency drift, reproducibility failures, or an external deployment environment requiring the fallback requirements file |
| CI workspace adoption | CI still installs Python dependencies from `backend_app/requirements.txt` and Node dependencies per service | Workspace lockfiles are now adopted by quality, SPA e2e, and deploy-build CI jobs; the Docker runtime image also uses the locked graph | A failed equivalence review or deployment environment that cannot consume workspace locks |
| Cross-service import boundaries | No automated check prevents unintended imports between Python and JavaScript service areas | A lightweight Python/Node boundary gate now runs in backend quality CI | A boundary exception is needed or a cross-service dependency incident occurs |
| Incremental build caching | No Turborepo/Nx orchestration is configured | CI now caches Next.js and BFF TypeScript build state with source-aware keys and reports cache hits in the job summary; full orchestration remains deferred | Hosted CI data shows insufficient cache benefit or CI build duration/service count materially increases enough to justify task-graph tooling |
| Frontend dependency security | Root npm audit retains one low development-only esbuild advisory beneath Vitest/Vite; service-local audits are clean | Critical/high findings were remediated, Next.js 16.3.3 is build-compatible, and the BFF has a scoped esbuild override; the remaining root advisory cannot be fixed globally without conflicting with SPA web's Vite 8 dependency | A production path is affected, the advisory severity changes, or a compatible Vitest/Vite upgrade is available |
| Cross-platform developer task runner | Common local orchestration depends on Windows `.bat` launchers | Root `justfile` now provides canonical `install`, `test`, `lint`, `typecheck`, `build`, `check`, container `start`/`stop`, and `health` commands; batch wrappers remain supported during migration | Contributors need macOS, Linux, or WSL support, or duplicated launcher behavior causes onboarding failures |
| Explicit repository boundary map | `src/`, `backend_app/`, `spa-bff/`, and `spa-web/` are valid boundaries but ownership and dependency direction are not obvious to new contributors | Document transport, domain, persistence, worker, BFF, and frontend ownership in `CODEBASE_MAP.md`, with a diagram matching the import-boundary gate | Boundary violations recur, or multiple contributors work across service areas |
| Documentation lifecycle and canonical-index hygiene | Enterprise documentation mixes canonical guides, compatibility redirects, historical plans, and active operational controls | `docs/DOCUMENTATION_LIFECYCLE.md` classifies Documentation HQ entries; primary operational guides record owner/review metadata; obsolete alpha guidance was removed; `scripts/check_docs_hq_links.py` now validates README HQ targets as well as backlinks. | Stale guidance is found, ownership changes, or the documentation set expands materially |
| Measured service-aware task graph | Workspace manifests and source-aware caches exist, but Turborepo/Nx adoption has not been justified by evidence | `docs/TASK_GRAPH_EVALUATION.md` records the current task graph, five-run measurement protocol, and promotion criteria; `scripts/measure_task_graph.py` and `just measure` collect comparable local timings. Repeated hosted-run measurements and external deployment observations remain outstanding | Service count, CI duration, or cache data demonstrates a material incremental-build benefit |
| Multi-tenant foundation | Zero tenant code exists (no `tenant_id` in schema/middleware) | Greenfield architecture, not reliability hardening; no multi-tenant requirement exists | An actual multi-tenant requirement appears (see enterprise roadmap deferred section) |
| UI feature-shell refactor | Some state boundaries mixed across flows | Frontend already decomposed (~75 files under `atlas-shell/`); refactor is churn without a team-scale payoff | Multiple contributors working the same frontend concurrently |

## Removed items (were stale or incorrect)

| Original item | Reason removed |
|---|---|
| Decompose AtlasShell (#4) | Already decomposed: ~75 files under `spa-web/src/components/atlas-shell/`. Finding was stale |
| Service-layer extraction (#6) | Already done: `crud.py` is a thin facade over sliced `crud_*_helpers.py`; services exist in `src/services/`, domain logic in `src/domain/` |
| Worker retries/idempotency (#8 core) | Already implemented: idempotency keys, retry classification, attempt limits, reaping. Only DLQ visibility remained (kept above, narrowed) |
| Test architecture happy-path gap (#12) | Factually wrong: 71 test files / ~480+ tests are heavily failure-oriented (circuit breaker, replay guards, lockouts, RBAC denials, dual-mode parity, e2e Playwright) |
| DX/pre-merge checks (#14) | Factually wrong: CI runs ~15 gates; `docs/templates/` exists |
| Contract source-of-truth package / ADRs (#1 partial) | Governance already enforced via export-contract gate, helper integrity gate, JSCPD, RBAC matrix; full ADR program not justified at this scale |

## Delivery view

### Suggested execution order

1. **Items 7–10: Data-access strategy hardening**
2. Maintain the completed P0 controls and repeat recurring drills on schedule
3. Then per enterprise roadmap: async ops guardrails, secret-store abstraction,
   migration policy checks

### Team capacity model

1. Single developer: execute items 7–10 sequentially, recording evidence after
   each boundary change.
1. Weekly checkpoint: update this backlog with observed effort and failure evidence.

### Risks and watchpoints

1. OpenAPI codegen drift from runtime schema if endpoints are generated during dev with
   non-deterministic ordering.
1. Secret rotation misconfiguration without operational rehearsal.
1. Incomplete observability attribution causing false-positive SLO breaches in
   low-traffic hours.

### Measurable success metrics

1. No production incident in one quarter caused by contract drift on a read path.
1. At least one complete key-rotation rehearsal completed within runbook.
1. SLO measurement script runs successfully in scheduled cadence.
1. 100% of dead terminal jobs discoverable through API before manual SQL fallback.

## Review cadence

1. Add a biweekly backlog checkpoint and close completed items with evidence links.
1. Archive resolved risk notes next to each item to preserve institutional memory.
1. Re-check the "P2 defer" list once operational maturity grows or team size changes.
