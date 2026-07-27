# Productionization Execution Backlog (Fresh Loop)

## Scope
Primary source: [docs/PRODUCTIONIZATION_AUDIT.md](docs/PRODUCTIONIZATION_AUDIT.md)

Status legend:
- `pending`
- `in_progress`
- `resolved`
- `blocked`
- `rejected`

## 2026-07-27

```yaml
- id: TOP10-01
  phase: Top 10 Actions Before Scaling
  title: Enforce distributed security state and private backend topology
  severity: critical
  problem: Production can still run with unsafe session/replay/rate state and backend ingress paths if config is incomplete.
  why_it_matters: This is a hard boundary for confidentiality, integrity, and safe horizontal scaling.
  recommended_change: make startup/config checks reject memory-backed security state and public backend targets in production-like modes.
  expected_benefit: Prevents production security regressions and lateral exposure.
  acceptance_criteria:
    - `scripts/check_deploy_config.py --mode runtime` fails when `OKR_BACKEND_SECURITY_STATE_BACKEND=memory` in production mode.
    - No public backend URL is accepted by deploy/runtime checks.
    - Verification evidence is committed in the work log.
  dependencies: []
  affected_modules:
    - backend_app/config.py
    - spa-bff/src/config.ts
    - scripts/check_deploy_config.py
    - tests/test_backend_request_signing.py
    - tests/test_check_deploy_config_script.py
  verification: ruff, targeted pytest
  status: resolved
  notes: Validated in this loop via runtime deploy-config/preflight checks; hardening checks already block memory-backed security state and runtime placeholder inputs, and no new regressions were introduced.

- id: TOP10-02
  phase: Top 10 Actions Before Scaling
  title: Add full-stack Docker Compose smoke test for critical journey
  severity: high
  problem: Current CI can pass while service wiring, session handoff, and job-path integrations are broken.
  why_it_matters: This is the highest-value regression blocker for deployment confidence.
  recommended_change: add a reproducible compose-backed smoke test validating health/read/mutation/job flow.
  expected_benefit: catches topology and config breakage before release.
  acceptance_criteria:
  - A single command starts required services from docker-compose and validates login, read, mutation, and job submission/polling.
    - Smoke test is CI-gated and fails the pipeline on wiring or compatibility regressions.
  dependencies: []
  affected_modules:
    - scripts/verify_resilience.py
    - deploy/docker/docker-compose.yml
    - tests/test_e2e_smoke.py
    - .github/workflows/ci.yml
  verification: compose run + pytest smoke target + CI
  status: resolved
  notes: Implemented compose-backed smoke runner in `scripts/verify_resilience.py` and critical route smoke file `tests/test_e2e_smoke.py`; wired to CI via `python scripts/verify_resilience.py --compose-smoke`.

- id: TOP10-03
  phase: Top 10 Actions Before Scaling
  title: Add PostgreSQL integration validation for migrations and authorization
  severity: high
  problem: SQLite-backed tests do not surface production DB-specific behavior and lock semantics.
  why_it_matters: Prevents production-only authorization, lock, and migration failures.
  recommended_change: add PostgreSQL-backed migration/RLS/RBAC verification profile.
  expected_benefit: Higher confidence that critical invariants survive production DB behavior.
  acceptance_criteria:
    - Migration, migration-order, and RLS tests run with PostgreSQL in CI profile.
    - Authorization and key integrity checks include realistic DB behavior.
  dependencies: []
  affected_modules:
    - scripts/*
    - tests/test_database_integrity.py
    - tests/test_authz_*
    - .github/workflows/ci.yml
  verification: CI-backed integration run
  status: resolved
  notes: Added and expanded PostgreSQL integration smoke coverage with migration-order/head checks, RLS enablement checks, advisory lock coverage, and DB key-integrity/constraint checks; wired via `python scripts/verify_postgresql_integration.py --ensure-docker-service` in CI.

- id: TOP10-04
  phase: Top 10 Actions Before Scaling
  title: Route/auth/allowlist contract checks for mutation security
  severity: high
  problem: Drift can occur between backend routes, auth matrix docs, and BFF allowlist entries.
  why_it_matters: Route drift is a direct security and behavior regression vector.
  recommended_change: keep generated/derived contract checks comparing backend routes, BFF allowlist, and auth matrix tests.
  expected_benefit: Prevents accidental mutation surface exposure.
  acceptance_criteria:
    - Mutation endpoint set coverage test remains green and fails on any missing route.
  - BFF allowlist mismatch is covered by automated verification.
  dependencies: []
  affected_modules:
    - tests/test_backend_mutation_auth_matrix.py
    - spa-bff/src/allowlist.ts
    - backend_app/main.py
  verification: targeted pytest
  status: resolved
  notes: Added a strict backend-route + BFF allowlist mutation contract test and aligned allowlist drift by adding `/v1/state/{key}` for state write coverage.

- id: TOP10-05
  phase: Top 10 Actions Before Scaling
  title: Standardize API error envelopes with stable codes and request IDs
  severity: medium
  problem: Public and internal errors are not consistently shaped across handlers.
  why_it_matters: Inconsistent failures increase MTTR and complicate monitoring triage.
  recommended_change: add shared error response normalizer and migrate mutation/read handlers to use it.
  expected_benefit: Predictable error handling for clients and operations.
  acceptance_criteria:
    - Critical backend and BFF paths return a consistent envelope with code/message/request_id.
    - Observability IDs propagate in error responses.
  dependencies:
    - TOP10-04
  affected_modules:
    - backend_app/main.py
    - spa-bff/src/server.ts
    - src/error_formats.py
    - tests/test_backend_observability.py
    - tests/test_api_contracts.py
  verification: ruff + targeted pytest + API contract checks
  status: resolved
  notes: BFF boundary emits structured envelopes (`code`, `error`, `request_id`) on login/proxy error paths while preserving existing detail/body fields for compatibility. Backend now emits the same standard envelope for HTTP, validation, and unhandled exceptions in middleware with request/correlation IDs.

- id: IMM-01
  phase: Immediate Roadmap
  title: Make production startup fail on missing/weak deploy-hardening invariants
  severity: critical
  problem: Some hardening settings rely on permissive defaults when incomplete.
  why_it_matters: Missing enforcement reduces the effectiveness of hardened deployments.
  recommended_change: centralize startup validation for token, cookie, signing, and URL safety invariants.
  expected_benefit: prevents unsafe runtime launch under production mode.
  acceptance_criteria:
    - Startup validation is deterministic and fails fast with explicit reasons.
  dependencies: []
  affected_modules:
    - backend_app/config.py
    - spa-bff/src/config.ts
  verification: config tests + startup-like validation tests
  status: resolved
  notes: Added startup-time BFF URL safety validation in `spa-bff/src/config.ts` so production hardening checks fail fast when backend API target is public/non-private. Updated config tests to cover public-host rejection and internal DNS acceptance.

- id: IMM-02
  phase: Immediate Roadmap
  title: Add minimal end-to-end mutation/auth route smoke assertion for compose stack
  severity: high
  problem: Current checks can pass without validating runtime route behavior.
  why_it_matters: route-level behavior (status/headers/payload) needs production-like assertion.
  recommended_change: add a lightweight smoke test that exercises one mutation + one read + one job poll.
  expected_benefit: catches integration breakage from route decomposition and config drift.
  acceptance_criteria:
    - Smoke run fails when any of login/read/mutation/job poll semantics regress.
  dependencies:
    - TOP10-02
  affected_modules:
    - tests/test_e2e_smoke.py
    - scripts/verify_resilience.py
    - .github/workflows/ci.yml
  verification: pytest e2e smoke + CI
  status: resolved
  notes: Added `tests/test_e2e_smoke.py` route-level smoke assertions for login/read/mutation/job poll and executed/CI-gated them through `python scripts/verify_resilience.py --compose-smoke`.

- id: IMM-03
  phase: Immediate Roadmap
  title: Add contract/behavior verification after API module extraction
  severity: medium
  problem: Router extraction can create accidental divergence from previous response contracts.
  why_it_matters: Preserves behavior while enabling modularization.
  recommended_change: add/extend contract tests around extracted router boundary modules.
  acceptance_criteria:
    - Mutation matrix and representative payload/response contracts remain green after refactors.
  dependencies:
    - ARCH-03
  affected_modules:
    - tests/test_backend_mutation_api.py
    - backend_app/routers/*.py
  verification: targeted pytest
  status: resolved
  notes: Added router-contract assertions that validate endpoint path/method/status/response-model stability and route-ownership to router modules after extraction. Added registration-entrypoint smoke test for all router modules.

- id: SHORT-01
  phase: Short-Term Roadmap
  title: Standardize error envelopes in critical frontend-backend boundary responses
  severity: medium
  problem: BFF and backend clients currently receive inconsistent non-happy-path payload shapes.
  why_it_matters: Increases stability for frontend error handling and observability.
  recommended_change: align error responses for auth/session/deny/validation paths with shared fields.
  expected_benefit: lower debugging time and safer UX handling under failures.
  acceptance_criteria:
    - Frontend boundary errors include `code`, `message`, and `request_id`.
  dependencies:
    - TOP10-05
  affected_modules:
    - spa-bff/src/server.ts
    - spa-bff/src/proxy.ts
    - backend_app/main.py
  verification: targeted unit/integration tests
  status: resolved
```

- id: TOP10-06
  phase: Top 10 Actions Before Scaling
  title: Add production dependency vulnerability gate in CI
  severity: high
  problem: Dependency vulnerabilities are not automatically enforced in CI and can remain in production dependencies.
  why_it_matters: Unscanned supply-chain risk undermines security posture despite hardened code-path controls.
  recommended_change: add `scripts/verify_dependency_scans.py` to backend CI and run `pip-audit` (Python) + `npm audit` (SPA packages) with severity threshold `high`.
  expected_benefit: early detection of exploitable dependency issues before merge; clear evidence trail for remediation.
  acceptance_criteria:
    - CI executes dependency scan step for Python and Node stacks.
    - The scan gate fails PRs when actionable findings are detected.
    - Skips are only allowed when tooling is unavailable, with explicit warnings.
  dependencies: []
  affected_modules:
    - scripts/verify_dependency_scans.py
    - .github/workflows/ci.yml
  verification: scripts + CI
  status: resolved
  notes: Added enforceable CI behavior. Scanner is now strict under CI (`CI=true` fails on missing scanners) while remaining warning-based locally. Added pip-audit installation step in CI workflow to reduce missing-tool false positives.

- id: SHORT-02
  phase: Short-Term Roadmap
  title: Enforce dependency license policy for Python and Node lockfiles
  severity: medium
  problem: A dependency can be secure but legally non-compliant or restricted by organizational policy.
  why_it_matters: Unreviewed licenses can delay production release, create legal exposure, and block enterprise adoption.
  recommended_change: add a shared CI license compliance gate for Python and Node dependencies using policy allowlist and lockfile-based evidence.
  expected_benefit: Prevents unsupported licenses before merge and creates an auditable policy gate.
  acceptance_criteria:
    - CI runs a license check for backend Python and SPA package-lock dependencies.
    - Violations for disallowed licenses fail the gate.
    - Missing/parse failures fail in CI but emit explicit diagnostic logs.
  dependencies: []
  affected_modules:
    - scripts/verify_dependency_licenses.py
    - .github/workflows/ci.yml
  verification: scripts
  status: resolved
  notes: Implemented and closed via `TOP10-07` dependency license policy execution in this fresh loop; scanner behavior now enforces CI hard-fail when tools or policy checks are unavailable.

- id: TOP10-07
  phase: Top 10 Actions Before Scaling
  title: Enforce dependency license policy for Python and Node dependencies
  severity: medium
  problem: Legal/compliance checks are missing for supply-chain dependencies, risking production release risk and enterprise governance violations.
  why_it_matters: Security-focused systems also need license governance and auditable policy compliance.
  recommended_change: add CI-level dependency-license compliance checks for Python and Node lockfiles with explicit allowlist/exception model.
  expected_benefit: blocks non-compliant license introductions before merge and keeps compliance evidence in the loop.
  acceptance_criteria:
    - CI executes `scripts/verify_dependency_licenses.py` with clear pass/fail behavior.
    - Disallowed licenses fail the gate.
    - Tooling/missing-scan failures are explicit and fail in CI.
  dependencies:
    - TOP10-06
  affected_modules:
    - scripts/verify_dependency_licenses.py
    - .github/workflows/ci.yml
    - PRODUCTIONIZATION_EXECUTION_BACKLOG.md
  verification: scripts + CI
  status: resolved
  notes: Added enforceable license policy gate with lockfile-based Node checks and pip-licenses-based Python checks, with scoped exceptions for known transitive packages.

- id: TOP10-08
  phase: Top 10 Actions Before Scaling
  title: Standardize structured JSON logs across backend, BFF, and worker
  severity: medium
  problem: Logging payloads are inconsistent between backend middleware, BFF boundary routes, and worker operations, limiting cross-service correlation.
  why_it_matters: Incident analysis slows when request IDs and statuses are not uniformly emitted across services.
  recommended_change: emit JSON-structured logs for request lifecycle and worker lifecycle events with correlation_id/request_id/method/route/status/error metadata.
  expected_benefit: enables cross-service correlation and faster MTTR using shared observability fields.
  acceptance_criteria:
    - Backend middleware and exception paths emit JSON envelopes containing `event`, `method`, `route`, `status`, `request_id`, `correlation_id`.
    - BFF logs request completion and key error branches with `event`, route/method, status, `request_id`, and `correlation_id`.
    - Worker emits structured observability event logs for claim/start/complete/failure paths using shared payload helpers.
  dependencies:
    - TOP10-05
  affected_modules:
    - backend_app/main.py
    - spa-bff/src/server.ts
    - backend_app/worker.py
    - tests/test_backend_observability.py
    - tests/test_worker_observability.py
    - spa-bff/test/server.test.ts
  verification: targeted pytest + vitest
  status: resolved
  notes: Implemented structured log events in backend request middleware/error handlers, BFF request/error logging hooks, and worker job lifecycle paths. Added regression tests to assert emitted JSON observability fields.

- id: ARCH-11
  phase: Audit Closure Loop
  title: Decompose remaining high-risk logic from `backend_app/main.py`
  severity: high
  problem: `backend_app/main.py` still owns significant behavior and authorization orchestration that should move into domain/services.
  why_it_matters: Large single-file ownership increases merge conflicts and behavior regression risk.
  recommended_change: extract remaining handler/service logic clusters into focused modules with stable delegates and contract tests.
  expected_benefit: lower change risk and clearer ownership boundaries.
  acceptance_criteria:
    - No new behavior changes after extraction.
    - Router and API contract tests remain green.
    - Domain helpers moved into service modules with explicit imports and minimal cross-file coupling.
  dependencies:
    - ARCH-03
  affected_modules:
    - backend_app/main.py
    - src/domain/*.py
    - backend_app/routers/*.py
  verification: targeted pytest + contract tests
  status: resolved
  notes: Loop 2 started 2026-07-27. Scope was extraction/decomposition cleanup in `backend_app/main.py` with compatibility-preserving wrappers to keep public contracts stable. Completed with acceptance criteria met; route/mutation/auth contract tests pass (`162 passed`) and regression behavior remains intact.

- id: DUAL-01
  phase: Audit Closure Loop
  title: Resolve direct DB vs Supabase API fallback behavior drift
  severity: high
  problem: Dual access paths can diverge in business behavior and authorization checks.
  why_it_matters: Divergence creates hidden production-only defects and policy exceptions.
  recommended_change: define one authoritative path or enforce cross-mode contract parity tests for all critical flows.
  expected_benefit: deterministic authorization and mutation/read behavior across deployment modes.
  acceptance_criteria:
    - Critical read/mutation flows have parity tests for direct DB and Supabase API modes.
    - A decision is documented (keep, deprecate, or remove fallback) and implemented with migration evidence.
  dependencies:
    - TOP10-01
  affected_modules:
    - src/services/supabase_api_mode.py
    - src/domain/*.py
    - tests
  verification: integration tests + mode comparison tests
  status: resolved
  notes: Closed in Loop 3 on 2026-07-27. Added `tests/test_dual_mode_parity.py` with cross-mode parity tests for critical mutation/query flows and verified deterministic behavior alignment across `is_supabase_api_mode_enabled` branches. Verification: `python -m pytest -q tests/test_dual_mode_parity.py` (7 passed).

- id: CRUD-01
  phase: Audit Closure Loop
  title: Reduce `src/crud.py` facade concentration and split domain services
  severity: high
  problem: `src/crud.py` still acts as broad orchestration surface.
  why_it_matters: Hard-to-maintain facade design slows safe evolution and masks ownership.
  recommended_change: move command/query ownership into explicit domain services with stable call surfaces.
  expected_benefit: clearer business boundary and lower regression coupling.
  acceptance_criteria:
    - New service modules own query/mutation orchestration slices.
    - Backward-compatible handlers in calling modules.
    - Remaining facade functions become narrow and explicit.
  dependencies:
    - ARCH-11
  affected_modules:
    - src/crud.py
    - src/domain/auth_service.py
    - src/domain/read_service.py
    - src/domain/mutation_service.py
  verification: targeted pytest
  status: resolved
  notes: Loop 3 completed in this cycle. Extracted shared CRUD contract surfaces into `src/domain/crud_contracts.py` (update allow-list sets, sentinel, auth bootstrap/config constants, model-binding names) and wired `src/crud.py` to consume these centrally while preserving legacy `_ALLOWED_*`, `_UNSET`, and auth constants as module compatibility aliases.

- id: OBS-02
  phase: Audit Closure Loop
  title: Complete operations observability stack: dashboards, alerts, and incident runbooks
  severity: medium
  problem: Logs/metrics exist but production-grade incident visibility and response docs are incomplete.
  why_it_matters: Detection and recovery speed is limited without alerting and runbook codification.
  recommended_change: add dashboards and alert definitions tied to queue, auth, worker, DB, and API health signals with documented response steps.
  expected_benefit: lower MTTR and clearer operator behavior in incidents.
  acceptance_criteria:
    - Dashboard definitions and alert rules exist for core platform signals.
    - Incident runbooks include at least migration rollback, credential rotation, and worker dead-letter/retry recovery.
  dependencies:
    - TOP10-08
  affected_modules:
    - backend_app/main.py
    - backend_app/worker.py
    - scripts
    - README.md
  verification: docs review + operational simulation evidence
  status: resolved
  notes: Closed in Loop 4 on 2026-07-27. Added `docs/OBSERVABILITY_AND_RUNBOOKS.md` with dashboard/alert/runbook definitions for API, BFF, worker, DB, auth, and audit domains. Added verification script `scripts/verify_observability_readiness.py` and linked artifacts from README and deployment operations guide.

- id: OPS-01
  phase: Audit Closure Loop
  title: Implement operational maturity for retention, partitioning, backup, and restore drills
  severity: medium
  problem: Retention/restore policies and DB growth controls are partially defined but not fully codified.
  why_it_matters: Data growth and recovery gaps become production incidents under load or incident.
  recommended_change: define and implement retention/partition strategy, backup restore drill checks, and admin restore workflows.
  expected_benefit: safer scale and recoverability posture.
  acceptance_criteria:
    - Retention/partition policy documented and implemented for growth-risk tables.
    - Backup restore drill tested in an environment path and logged.
    - Restore command paths are validated in CI or scripted validation.
  dependencies: []
  affected_modules:
    - docs/PRODUCTIONIZATION_AUDIT.md
    - scripts
    - backend_app/worker.py
    - src/models.py
    - tests
  verification: scripted drill + evidence log
  status: resolved
  notes: Closed in this loop. Added `docs/OPS_READINESS_AND_RECOVERY_GUIDE.md` with retention, partition strategy, and restore drill contracts; added `alembic/versions/bc1d2e3f4a5b_ops01_growth_table_indexes.py` with retention/query indexes for `async_job` and `audit_event` (PostgreSQL); added `scripts/verify_ops01_readiness.py` and `tests/test_ops01_readiness.py` for codified evidence and backup-drill roundtrip validation.

- id: TEST-01
  phase: Audit Closure Loop
  title: Expand critical end-to-end Playwright coverage
  severity: medium
  problem: Core role-based browser journeys are still thinner than production risk profile.
  why_it_matters: UI behavior regressions can bypass unit-level protections.
  recommended_change: add stable role-based critical-path E2E flows for create/update/check-in/timer/jobs.
  expected_benefit: higher confidence across release cycles for user-facing critical paths.
  acceptance_criteria:
    - At least one admin, manager, and member happy-path suite is stable in CI.
    - Coverage includes timer + check-in + mutation + one AI/PDF or job path.
  dependencies:
    - TOP10-07
  affected_modules:
    - spa-web
    - spa-bff
    - backend_app/main.py
  verification: Playwright CI smoke + regression matrix
  status: resolved
  notes: Completed role-parameterized SPA harness in `tests/test_e2e_playwright_spa_login_to_atlas.py` for admin/manager/member happy paths (timer, check-in, weekly report job action, role-based admin gating, admin mutation flow). Seed data was stabilized so each role has one owned goal/objective/KR/task in one shared active cycle (`E2E Core Cycle`), timer options are now populated for all roles, and timer path now waits for non-placeholder active-task options with safe fallback behavior before selection and assertion.

- id: MOD-12
  phase: Audit Closure Loop
  title: Final helper integrity cleanup in `backend_app/main.py`
  severity: medium
  problem: Some scope/auth helper implementations in `backend_app/main.py` were still duplicated, weakening single-source ownership.
  why_it_matters: duplicates in high-risk security path logic increase regression and drift risk.
  expected_benefit: one canonical implementation for scope/auth helpers in `backend_app/scope_resolution.py` with compatibility wrappers in `main.py`.
  acceptance_criteria:
    - `backend_app/main.py` delegates helper logic for `_resolve_effective_cycle_id_for_scope`, `_require_admin_actor_scope`, and `_require_admin_or_manager_actor_scope` to `backend_app/scope_resolution.py`.
    - `__all__` list remains stable and no new helper exports are introduced during cleanup.
  dependencies:
    - MOD-11
  affected_modules:
    - backend_app/main.py
    - backend_app/scope_resolution.py
  verification: targeted review of duplicated definitions
  status: resolved
  notes: Removed duplicate implementations from `backend_app/main.py` for effective cycle resolution and admin/admin-or-manager scope checks; replaced with thin wrapper delegates to `backend_app/scope_resolution.py` and cleaned an unused scope-resolution import.

- 2026-07-27: MOD-11 completed — extracted duplicated scope/actor/cycle helper logic out of `backend_app/main.py` into `backend_app/scope_resolution.py` and removed local duplicates; tests passed: 13 in `tests/test_backend_observability.py`, `tests/test_backend_error_envelope.py`, `tests/test_worker_observability.py`.
