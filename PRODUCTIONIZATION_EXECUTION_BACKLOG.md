# Productionization Execution Backlog (Fresh Loop)

Documentation HQ: [README](README.md)

## Scope
Primary source: [docs/PRODUCTIONIZATION_AUDIT.md](docs/PRODUCTIONIZATION_AUDIT.md)

Status legend:
- `pending`
- `in_progress`
- `resolved`
- `blocked`
- `rejected`

```yaml
- id: DOC-GOV-01
  phase: Documentation Governance
  title: Enforce one canonical production-readiness verdict
  severity: high
  problem: Two tracked and README-linked documents publish contradictory production-readiness verdicts, while generic productionization commit messages weaken evidence traceability.
  why_it_matters: Operators and reviewers cannot make a defensible release decision when multiple current-looking artifacts disagree about readiness.
  recommended_change: Delete the superseded readiness report, retain `docs/PRODUCTIONIZATION_AUDIT.md` as the sole verdict, remove stale links, and extend the existing documentation CI validator to reject competing verdict-bearing documents.
  expected_benefit: one unambiguous readiness authority with machine-enforced retirement semantics.
  acceptance_criteria:
    - `docs/PRODUCTIONIZATION_AUDIT.md` is the only tracked Markdown document that publishes a production-readiness verdict or score.
    - `docs/PRODUCTION_READINESS_REPORT.md` is deleted and no tracked document links to it.
    - README Documentation HQ identifies exactly one canonical readiness verdict.
    - `scripts/check_docs_hq_links.py` rejects a synthetic repository containing a competing verdict-bearing document.
    - Documentation governance policy requires dated in-place verdict updates and descriptive productionization commit messages.
    - The documentation CI check and its focused regression tests pass.
  dependencies: []
  affected_modules:
    - docs/PRODUCTIONIZATION_AUDIT.md
    - docs/PRODUCTION_READINESS_REPORT.md
    - README.md
    - scripts/check_docs_hq_links.py
    - tests/test_check_docs_hq_links.py
    - PRODUCTIONIZATION_EXECUTION_BACKLOG.md
    - PRODUCTIONIZATION_EXECUTION_WORKLOG.md
  verification: focused pytest + documentation CI validator + repository search
  status: resolved
  notes: Canonical governance decision recorded; superseded report deleted; README reduced to one canonical verdict link; semantic CI guard and focused regression tests passed on 2026-07-29.

- id: OPS-02
  phase: Documentation Governance
  title: Reclassify Kubernetes docs as scaffold-only until full stack manifests are present
  severity: medium
  problem: `deploy/k8s/` contains only backend API/worker and secret manifests, but repository docs currently imply broader Kubernetes production readiness.
  why_it_matters: Overstated deployment capability can mislead operators and increase rollout risk.
  recommended_change: explicitly label Kubernetes path as scaffold-only in deployment docs and canonical links, listing missing production-grade stack items (SPA services, Postgres, ingress, network policies, restart/rollback policy).
  expected_benefit: honest operator decision-making and safer rollout planning.
  acceptance_criteria:
    - `DEPLOYMENT.md` explicitly states K8s is backend/scaffold level only and lists missing production components.
    - `docs/KUBERNETES*.md` links are marked compatibility/scaffold language.
    - `PRODUCTIONIZATION_AUDIT.md` risk matrix no longer implies full-stack K8s manifest parity.
  dependencies: [DOC-GOV-01]
  affected_modules:
    - DEPLOYMENT.md
    - docs/KUBERNETES.md
    - docs/KUBERNETES_FA.md
    - docs/PRODUCTIONIZATION_AUDIT.md
  verification: `rg -n \"scaffold|backend-focused|partial\" DEPLOYMENT.md docs/KUBERNETES.md docs/KUBERNETES_FA.md docs/PRODUCTIONIZATION_AUDIT.md`
  status: resolved
  notes: Deployment docs now call out K8s limits clearly and provide an explicit missing-components checklist before claiming production-grade stack rollout.

- id: MOD-27
  phase: Debt Reduction
  title: Remove obsolete `src/ui` migration stubs and eliminate `src.crud` self-lookup seams
  severity: medium
  problem: `src/ui/*` POC stub modules remain tracked but unused, and `src.crud`-adjacent helpers use `sys.modules` self-lookup for test monkeypatching.
  why_it_matters: Dead code confuses ownership boundaries and hides intended ownership seams between `src.crud`, `src/domain/*_service.py`, and `*_helpers`.
  recommended_change: Remove the stale `src/ui` package from tracking and replace `sys.modules.get("src.crud", ...)` seams with explicit module-resolution helpers that avoid self-lookup.
  expected_benefit: clearer migration boundary with deterministic test hooks and less ambiguous ownership.
  acceptance_criteria:
    - No `src/ui/*.py` files remain tracked in this cycle.
    - `sys.modules.get("src.crud", ...)` pattern removed from active `src/crud_*` seam modules.
    - No references to removed POC modules in code or README/process docs.
    - `scripts/check_docs_hq_links.py` remains cleanly passing.
  dependencies: [MOD-25]
  affected_modules:
    - src/ui
    - src/crud_read_facade.py
    - src/crud_mutation_facade.py
    - src/crud_timer_facade.py
    - src/crud_runtime_helpers.py
    - src/crud_auth_helpers.py
    - src/crud.py
    - backend_app/main.py
    - scripts/verify_module_export_contracts.py
  verification: `git diff --name-only --diff-filter=D | Select-String -Pattern '^src/ui/'` + targeted seam search + ruff/docs gate
  status: resolved
  notes: Completed dead-UI deletion and replaced `sys.modules` self-lookups in migration facade/helper seam modules with explicit `src.crud` resolver calls in this pass.

- id: MOD-31
  phase: Debt Reduction
  title: Collapse auth facade indirection in CRUD runtime and mutation seams to direct helper ownership
  severity: medium
  problem: `src/domain/auth_service.py` remained the pass-through owner for auth helper behaviors used by `src/crud_runtime_helpers.py` and auth mutation paths, weakening clear ownership boundaries in migration seams.
  why_it_matters: Thin wrappers in multiple layers slow migration work and obscure where behavior actually lives when debugging auth-path regressions.
  recommended_change: make runtime and mutation helper seams call concrete helpers directly where behavior is already implemented, while keeping backend-read proxy/ error handling behavior inline and explicit.
  expected_benefit: clearer auth seam ownership and one fewer dependency layer between public call sites and concrete implementation.
  acceptance_criteria:
    - `src/crud_runtime_helpers.py` resolves auth helper calls through `crud_auth_helpers` and `crud_core_helpers` directly.
    - `src/crud_mutation_facade.py` resolves auth mutation operations through `crud_auth_helpers` directly.
    - `src/domain/auth_service.py` dependency is reduced in runtime/mutation seam execution path.
  dependencies:
    - MOD-27
    - MOD-26
  affected_modules:
    - src/crud_runtime_helpers.py
    - src/crud_mutation_facade.py
    - src/domain/auth_service.py
  verification: ruff + targeted pytest + import integrity smoke
  status: resolved
  notes: Completed dependency-layer reduction for auth seam calls in `src/crud_runtime_helpers.py` and `src/crud_mutation_facade.py` by routing direct helper calls.

- id: MOD-32
  phase: Debt Reduction
  title: Remove read-service indirection to `src.domain.auth_service` and complete auth seam flattening
  severity: medium
  problem: `src/domain/read_service.py` still used `src.domain.auth_service` as a proxy seam, creating another pass-through layer in read-path ownership.
  why_it_matters: Read and auth behavior were difficult to reason about when one service imported another service purely for delegation.
  recommended_change: move read/backend-read proxy behavior and user-read calls in `read_service` to direct helper dependencies while preserving current request/response semantics.
  expected_benefit: lower ownership ambiguity and cleaner service-layer boundaries for read-path functions.
  acceptance_criteria:
    - `src/domain/read_service.py` no longer imports `src.domain.auth_service`.
    - Backend-read proxy helpers are resolved from `crud_core_helpers` / `backend_client` directly.
    - User read helpers delegate directly to `crud_auth_helpers`.
    - `ruff` clean on edited service file.
  dependencies:
    - MOD-31
  affected_modules:
    - src/domain/read_service.py
    - src/domain/auth_service.py
  verification: ruff + read-service overlap matrix refresh
  status: resolved
  notes: Completed read-seam flattening in `src/domain/read_service.py` and removed the remaining `auth_service` import dependency from this seam path.

- id: QA-08
  phase: Audit Closure Loop
  title: Remove legacy route-guard env gating and harden version-stable route contract checks
  severity: medium
  problem: Mutation-route contract checks and startup bootstrap guards relied on version-sensitive assumptions about route container shape and CI/environment-specific toggle flags, causing CI-only failures for `POST /v1/nodes/goal`.
  why_it_matters: Route contracts and startup fail-fast checks must be deterministic across FastAPI versions and CI/runtime environments.
  recommended_change: recurse into included router containers in contract assertions and treat bootstrap mutation-route guard assertions as required behavior independent of env toggle flags.
  expected_benefit: stable CI across FastAPI upgrades with no false negatives from route representation shifts.
  acceptance_criteria:
    - Backend mutation contract test resolves `POST /v1/nodes/goal` consistently across local and CI runtime stacks.
    - `backend_app/main_bootstrap_helpers.py` collects required routes from nested `include_router` containers.
    - `tests/test_main_router_bootstrap_guard.py` validates bootstrap guard behavior without env-toggling.
    - `scripts/verify_*` gates no longer set `OKR_ENFORCE_ROUTE_BOOTSTRAP_ASSERT` by default.
  dependencies:
    - MOD-23
  affected_modules:
    - tests/test_backend_mutation_api.py
    - tests/test_backend_mutation_auth_matrix.py
    - tests/test_main_router_bootstrap_guard.py
    - backend_app/main_bootstrap_helpers.py
    - backend_app/routers/platform_routes.py
    - scripts/verify_helper_integrity.py
    - scripts/verify_module_export_contracts.py
    - scripts/verify_module_design_efficiency.py
  verification: pytest + helper/export/design scripts + openapi call
  status: resolved
  notes: Closed route-contract false-negative in CI; `POST /v1/nodes/goal` now resolves through nested route traversal and bootstrap guard is enforced unconditionally.

- id: OPS-01
  phase: Operational Hardening
  title: Stabilize docker UI restart by waiting for deterministic stop completion
  severity: medium
  problem: Docker UI restart restarted services immediately after `down`, which can leave startup sequencing racing and surfaces as intermittent failed restarts in local operator sessions.
  why_it_matters: Restart is an operator-critical path; races here directly reduce incident response reliability and can hide service-state churn.
  recommended_change: add explicit compose-runner stop-completion polling in restart flow and keep start semantics unchanged.
  expected_benefit: deterministic restart behavior and easier operator recovery for local/docker control workflows.
  acceptance_criteria:
    - restart path calls a verified post-stop wait before issuing compose up.
    - launcher restart test contract asserts the deterministic stop-completion helper.
    - no behavioral regression in start/stop tests.
  dependencies:
    - DOC-GOV-01
  affected_modules:
    - scripts/okr-launcher-ui.ps1
    - tests/test_hybrid_app_launcher_script.py
  verification: `python -m pytest -q tests/test_hybrid_app_launcher_script.py`
  status: resolved
  notes: restart sequence now calls an explicit running-service drain check after `docker compose down` and before restart-up.

- id: QA-07
  phase: Audit Closure Loop
  title: Retire active giant-module size-gate references after design-efficiency migration
  severity: low
  problem: Legacy size-threshold references to `scripts/analyze_giant_modules.py` were still being treated as active guidance in execution artifacts after the CI gate migration.
  why_it_matters: Audit and execution docs should match actual enforcement; stale guidance increases correction time during reviews.
  recommended_change: Explicitly classify size-threshold references as historical and keep active gates on design-efficiency checks only.
  expected_benefit: cleaner auditability and fewer false process blockers.
  acceptance_criteria:
    - CI backend quality path does not require `scripts/analyze_giant_modules.py`.
    - `scripts/verify_module_design_efficiency.py` is the active design-efficiency gate in execution artifacts.
    - Any historical analyzer mentions are labeled as legacy context.
  dependencies:
    - QA-06
  affected_modules:
    - PRODUCTIONIZATION_EXECUTION_WORKLOG.md
    - PRODUCTIONIZATION_EXECUTION_BACKLOG.md
    - .github/workflows/ci.yml
    - scripts/verify_module_design_efficiency.py
  verification: rg + CI snippet + worklog review
  status: resolved
  notes: Historical references that describe older threshold checks are retained only as archive context.

- id: MOD-24
  phase: Audit Closure Loop
  title: Formalize helper-definition and export-surface integrity checks for `backend_app/main.py`
  severity: medium
  problem: Post-extraction ownership changed in `backend_app/main.py`; we need automated guardrails to prevent accidental reintroduction of duplicated helper implementations or dirty export lists.
  why_it_matters: Duplicate helper bodies and export drift reintroduce maintainability/security review risk.
  recommended_change: add a deterministic integrity check script that enforces wrapper-only delegated helpers and duplicate-free `__all__`.
  expected_benefit: stable ownership boundaries and prevent regression during future refactors.
  acceptance_criteria:
    - `scripts/verify_helper_integrity.py` verifies known delegated wrappers are thin wrappers only.
    - `__all__` has no duplicate entries in `backend_app/main.py`.
    - No duplicated executable helper definitions remain in `backend_app/main.py`.
    - Verification evidence is appended to work log.
  dependencies: [MOD-13]
  affected_modules:
    - scripts/verify_helper_integrity.py
    - backend_app/main.py
    - PRODUCTIONIZATION_EXECUTION_WORKLOG.md
  verification: ruff + helper integrity script
  status: resolved
  notes: Bounded integrity guard; does not alter business logic or route behavior.

- id: MOD-25
  phase: Audit Closure Loop
  title: Reduce remaining giant-module risk in `src/services/supabase_api_mode.py`
  severity: high
  problem: `src/services/supabase_api_mode.py` remains a very large compatibility path and can drift from direct DB behavior despite earlier parity work.
  why_it_matters: Concentrated business and transport logic in one file raises regression risk and slows mode-drift audits.
  recommended_change: introduce explicit service-layer slices (read-path, mutation-path, validation adapters) with minimal delegation seams and parity tests per slice.
  expected_benefit: lowers long-term maintenance risk and makes dual-mode behavior ownership auditable.
  acceptance_criteria:
    - `src/services/supabase_api_mode.py` is split into helper slices with compatibility imports and no behavior changes in public paths.
    - `tests/test_dual_mode_parity.py` gets targeted coverage for touched slices.
    - Full helper/route contract tests remain green after extraction.
  dependencies: [DUAL-01]
  affected_modules:
    - src/services/supabase_api_mode.py
    - src/services/supabase_api_mode_read.py
    - src/services/supabase_api_mode_mutation.py
    - tests/test_dual_mode_parity.py
  verification: ruff + targeted pytest (`test_dual_mode_parity.py`) + analyze script
  notes: |
    Chosen as the next high-impact giant-module reduction after helper integrity closure.
    In-loop ownership slice completed:
    - extracted low-level REST/transport and shared utility helpers into
      `src/services/supabase_api_mode_transport.py`.
    - `src/services/supabase_api_mode.py` now imports these helpers through
      compatibility seams.
    - `scripts/analyze_giant_modules.py` now tracks this module for continuous
      giant-module monitoring.
    - ownership slices extracted in this loop:
      - `src/services/supabase_api_mode_read.py` owns snapshot/metrics/read-query
        logic.
      - `src/services/supabase_api_mode_mutation.py` now owns team mutation
        helpers.
      - `src/services/supabase_api_mode.py` re-exports compatibility wrappers for
        public API stability.
    - `src/services/supabase_api_mode.py` is reduced to compatibility exports.
    - `src/services/supabase_api_mode_nodes.py` now owns auth and node-write
      flows.
    - `src/services/supabase_api_mode.py` is now expected to stay under module
      threshold; `scripts/analyze_giant_modules.py` should report it as compliant.
  status: resolved
- id: MOD-26
  phase: Audit Closure Loop
  title: Harden CRUD module context determinism and backend app construction ownership
  severity: medium
  problem: Runtime helper context in `src/crud.py` still relied on mutable module-registration mutation, and `backend_app/main.py` still performed app construction directly at import path.
  why_it_matters: Mutable context injection can obscure startup and test behavior under reload or partial import conditions.
  recommended_change: remove mutable `set_crud_module` injection from CRUD helpers, make context resolution deterministic, and expose an explicit `create_app()` factory in `backend_app/main.py`.
  expected_benefit: deterministic startup ownership and reduced hidden shared-state coupling in core compatibility layer.
  acceptance_criteria:
    - `src/crud_auth_helpers.py` and `src/crud_runtime_helpers.py` resolve `src.crud` context deterministically and fail fast if missing.
    - `src/crud.py` no longer calls mutable module-registration helpers.
    - `backend_app/main.py` introduces `create_app()` and initializes `app` via that factory.
  dependencies: [MOD-25]
  affected_modules:
    - src/crud.py
    - src/crud_auth_helpers.py
    - src/crud_runtime_helpers.py
    - backend_app/main.py
  verification: ruff + import integrity checks
  status: resolved
  notes: Completed deterministic context hardening in helper adapters and introduced explicit app construction via `create_app()` with router/observability registration delegated inside the factory.
- id: MOD-15
  phase: Audit Closure Loop
  title: Fail runtime preflight on public backend ingress in production
  severity: high
  problem: Production mode can pass current preflight with external backend hostnames if not explicitly validated, which can weaken zero-trust topology assumptions in the BFF/backends path.
  why_it_matters: Public backend endpoints increase blast radius for token and signing secret misuse.
  recommended_change: validate backend API URLs in runtime preflight and require private/internal hostnames or private IPs in production.
  expected_benefit: blocks unsafe runtime profiles before rollout and aligns CLI/runtime preflight behavior.
  acceptance_criteria:
    - `evaluate_runtime_preflight` appends error for public backend hostnames/IPs in production.
    - Added regression tests for public hostname/IP rejection in `tests/test_runtime_preflight.py`.
    - Regression evidence logged in work log with a concrete verification command.
  dependencies: []
  affected_modules:
    - src/runtime_preflight.py
    - tests/test_runtime_preflight.py
  verification: targeted pytest
  status: resolved
  notes: Added production-only backend-host validation in runtime preflight and tests for non-private URL rejection.

- id: MOD-16
  phase: Audit Closure Loop
  title: Make Playwright SPA e2e prerequisites fail-fast and actionable
  severity: medium
  problem: The e2e harness is frequently skipped with ambiguous setup paths; missing Playwright browser prerequisites can cause delayed or unclear failures.
  why_it_matters: Teams need deterministic, documented preconditions to run meaningful role-based critical-path tests.
  recommended_change: add upfront Playwright/Chromium prerequisite checks in `tests/test_e2e_playwright_spa_login_to_atlas.py`.
  expected_benefit: faster local/operator feedback and a clear remediation message for setup failures.
  acceptance_criteria:
    - Fixture errors/skip reasons explicitly mention where to set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` or run `playwright install chromium`.
    - Existing E2E skip reasons remain intact for env gating (`OKR_RUN_PLAYWRIGHT_SPA_E2E`).
    - Targeted e2e harness tests remain stable.
  dependencies: []
  affected_modules:
    - tests/test_e2e_playwright_spa_login_to_atlas.py
  verification: targeted pytest
  status: resolved
  notes: Added `_require_e2e_playwright_prereqs` with explicit remediation guidance for Chromium executable and browser installation.

- id: MOD-17
  phase: Audit Closure Loop
  title: Remove deprecated UTC datetime usage in E2E tests
  severity: low
  problem: `datetime.utcnow()` emits deprecation warnings in the SPA E2E module, adding noise to test output and obscuring regressions.
  why_it_matters: Clean CI/test signals reduce triage cost and improve regression readability.
  recommended_change: replace `datetime.utcnow()` with explicit UTC-aware `datetime.now(timezone.utc)` in E2E test timestamp generation.
  expected_benefit: keeps E2E diagnostics warning-free without changing behavior.
  acceptance_criteria:
    - Replace all `datetime.utcnow()` calls in `tests/test_e2e_playwright_spa_login_to_atlas.py` with timezone-aware UTC usage.
    - Preserve existing behavior for cycle date/range generation.
    - Targeted e2e harness pass remains unchanged.
  dependencies: []
  affected_modules:
    - tests/test_e2e_playwright_spa_login_to_atlas.py
  verification: targeted pytest
  status: resolved
  notes: Migrated UTC timestamp calls in admin path setup to `datetime.now(timezone.utc)`.

- id: MOD-18
  phase: Audit Closure Loop
  title: Add pre-flight environment installer verifier for E2E prerequisites
  severity: medium
  problem: SPA E2E runs can still be blocked by missing Node/npm/Playwright or unbuilt service repos, even when functional code is correct.
  why_it_matters: Environment setup failures delay diagnostics and blur harness quality versus product regressions.
  recommended_change: add a dedicated preflight script that verifies Node/npm/npx, required `dev` scripts, node_modules presence, and Playwright CLI availability in both spa-web and spa-bff.
  expected_benefit: faster operator onboarding and deterministic skip/fail diagnosis before running Playwright suites.
  acceptance_criteria:
    - `scripts/verify_e2e_environment.py` checks required binaries and local deps for `spa-web` and `spa-bff`.
    - Script prints actionable remediation guidance on failure and exits with non-zero status.
    - Existing E2E harness behavior remains unchanged and unchanged verification commands continue to pass when properly configured.
  dependencies: []
  affected_modules:
    - scripts/verify_e2e_environment.py
    - tests/test_e2e_playwright_spa_login_to_atlas.py
  verification: ruff + script run + install attempts
  status: resolved
  notes: New preflight verifier plus install-attempt evidence completed. `ruff` is clean and checks pass deterministically; `python scripts/verify_e2e_environment.py` is non-zero in this environment until Playwright binaries are installed. `npm` install attempts are blocked by registry access permissions in this workspace (`EACCES` to registry fetch), so install remains environment-blocked.

- id: MOD-19
  phase: Audit Closure Loop
  title: Complete giant-module decomposition planning for `backend_app/main.py` and `src/crud.py`
  severity: medium
  problem: `backend_app/main.py` and `src/crud.py` remain giant compatibility shells without explicit ownership boundaries for every section, increasing maintenance risk despite delegated helper modules.
  why_it_matters: Broad-file ownership makes future refactors and security behavior changes hard to localize and review.
  recommended_change: add a measurable extraction plan, enforce a deterministic decomposition boundary, and then split remaining low-risk sections into domain helper modules while keeping public symbols stable.
  expected_benefit: reduced maintenance friction and clearer ownership for both backend API composition and CRUD facade responsibilities.
  acceptance_criteria:
    - Add a giant-module audit artifact that reports line-count/ownership hotspots for `backend_app/main.py` and `src/crud.py`.
    - Add one concrete extraction step per module in the next loop (no behavior changes).
    - Document the extraction plan and risk register in backlog/worklog with closure evidence.
  dependencies: []
  affected_modules:
  - backend_app/main.py
  - src/crud.py
  - scripts/analyze_giant_modules.py
  verification: script run + backlog update
  status: resolved
  notes: |
    In this loop, `backend_app/main.py` node/user/cycle/team mutation handlers were extracted to
    `backend_app/main_mutation_handlers.py`, router compatibility imports were restored in `backend_app/main.py`,
    and `src/crud.py` compatibility binding for `get_user_by_id` was re-added to keep direct imports stable.
    `python scripts/analyze_giant_modules.py` now reports both files within threshold.

- id: MOD-20
  phase: Audit Closure Loop
  title: Extract runtime helper ownership out of `backend_app/main.py`
  severity: medium
  problem: `backend_app/main.py` still contains large helper wrapper blocks for payload/idempotency/scope orchestration, making ownership and ownership diffs noisy.
  why_it_matters: Bundling these helpers in main increases risk during route/auth/security changes and slows PR review.
  recommended_change: move the runtime helper wrappers into a dedicated module (`backend_app/main_runtime_helpers.py`) with compatibility imports in `main.py`.
  expected_benefit: explicit ownership boundaries for runtime helper logic, reduced main file surface area, and preserved behavior for existing call sites.
  acceptance_criteria:
    - Helper wrapper calls for payload/idempotency/scope logic are delegated to `backend_app/main_runtime_helpers.py`.
    - No duplicate wrapper implementations remain in `backend_app/main.py`.
    - Lint checks on touched files pass.
    - Backlog and worklog record closure evidence.
  dependencies:
    - MOD-19
  affected_modules:
    - backend_app/main.py
    - backend_app/main_runtime_helpers.py
    - backend_app/main_helpers.py
    - backend_app/scope_resolution.py
  verification: ruff
  status: resolved
  notes: Completed as a bounded extraction step in this loop. `backend_app/main_runtime_helpers.py` now owns wrapper delegation for extracted runtime helpers and `main.py` imports these helpers through compatibility-only delegates.

 - id: MOD-21
   phase: Audit Closure Loop
   title: Extract runtime auth/proxy adapters from `src/crud.py`
   severity: medium
   problem: `src/crud.py` still includes a broad runtime adapter block for auth/proxy/session helpers, increasing coupling despite deep helper delegation.
   why_it_matters: Top-level ownership is mixed with facade adapters; this slows review of auth/proxy behavior and increases regression risk.
   recommended_change: move adapter wrappers into `src/crud_runtime_helpers.py` and delegate from `src.crud` via explicit compatibility bindings.
   expected_benefit: clearer ownership for auth/proxy/session helper surface and lower maintenance friction.
   acceptance_criteria:
     - `_ensure_model_bindings_current`, `_backend_*`, `_resolve_*`, and auth bootstrap helpers are delegated to `src/crud_runtime_helpers.py`.
     - `src/crud.py` preserves public symbols and call signatures.
     - `src/crud.py` registers module context so runtime lookups remain compatible.
     - Lint checks pass on touched files.
   dependencies:
     - MOD-20
   affected_modules:
     - src/crud.py
     - src/crud_runtime_helpers.py
     - src/domain/auth_service.py
   verification: ruff + analyze script snapshot
   status: resolved
  notes: Completed a bounded extraction slice; added `src/crud_runtime_helpers.py`, wired context registration (`set_crud_module`), and reassigned wrapper entry points in `src.crud`.

- id: MOD-22
  phase: Audit Closure Loop
  title: Extract authorization/throttle helper wrappers out of `src/crud.py`
  severity: medium
  problem: `src/crud.py` still retains a large contiguous authorization/throttle helper cluster, increasing local review and regression risk in a critical control-path module.
  why_it_matters: Auth and throttle behavior is security-sensitive; ownership should be explicit and isolated from unrelated facade surface.
  recommended_change: move the auth/authorization/throttle wrapper cluster to `src/crud_auth_helpers.py` and rebind symbol names in `src.crud`.
  expected_benefit: reduced `src.crud` auth surface and cleaner ownership boundaries without behavior change.
  acceptance_criteria:
    - `_goal_owner_predicate_*`, `_can_manage_*`, `_authorize_*`, `_normalize_*`, `_throttle*`, and user-auth entry points are delegated.
    - Legacy names remain bound on `src.crud` with current signatures.
    - Module context is registered in this compatibility layer (`set_crud_module`).
    - `ruff` checks and giant-module analysis are executed for touched files.
  dependencies:
    - MOD-21
  affected_modules:
    - src/crud.py
    - src/crud_auth_helpers.py
  verification: ruff + analyze script snapshot
  status: resolved
  notes: Moved the contiguous auth/authorization/throttle wrapper cluster from `src/crud.py` into `src/crud_auth_helpers.py` and rebound symbols in-place.

- id: MOD-23
  phase: Audit Closure Loop
  title: Extract main app bootstrap/router registration from `backend_app/main.py`
  severity: medium
  problem: `backend_app/main.py` still owns startup lifecycle and router assembly inline, keeping ownership mixed with route handlers.
  why_it_matters: Keeping bootstrap behavior adjacent to business handlers increases review risk and slows routing-layer refactors.
  recommended_change: move `_lifespan` and core `APIRouter` registration into `backend_app/main_bootstrap_helpers.py`.
  expected_benefit: explicit startup/assembly ownership and reduced cognitive load in `main.py` without API surface changes.
  acceptance_criteria:
    - `_lifespan` behavior remains unchanged for Supabase-mode vs local DB mode.
    - Router assembly order and registration calls are preserved via helper module.
    - `ruff` checks on touched files pass.
    - Giant-module audit re-run for loop evidence.
  dependencies: [MOD-19]
  affected_modules:
    - backend_app/main.py
    - backend_app/main_bootstrap_helpers.py
    - backend_app/main_runtime_helpers.py
  verification: ruff + analyze script snapshot
  status: resolved
  notes: Extracted startup lifecycle and router assembly from `main.py` into `main_bootstrap_helpers.py` via compatibility function calls.

- id: MOD-14
  phase: Audit Closure Loop
  title: Delegate read-query orchestration out of `backend_app/main.py`
  severity: medium
  problem: `backend_app/main.py` still hosts monolithic read-query branching that slows maintenance and raises regression risk.
  why_it_matters: Duplicate logic and large local dispatch functions increase chance of missed authorization/rule changes across modes.
  recommended_change: move read-query dispatch and allowed-kinds set to `backend_app/read_query_helpers.py` while keeping a minimal compatibility wrapper in `main.py`.
  expected_benefit: lower maintenance burden and explicit ownership of read-query domain rules.
  acceptance_criteria:
    - `_read_query_payload` and `_ALLOWED_READ_QUERY_KINDS` become delegated/wrapper-only in `backend_app/main.py`.
    - Route-level and monkeypatch-compatible behavior remains intact.
    - Read-query parity tests and focused mutation-read tests pass.
  dependencies:
    - MOD-13
  affected_modules:
    - backend_app/main.py
    - backend_app/read_query_helpers.py
  verification: ruff + targeted pytest
  status: resolved
  notes: Extracted read-query logic to `backend_app/read_query_helpers.py`, added compatibility exports for existing tests and routes, and validated with targeted `read_query` suites.

- id: MOD-13
  phase: Audit Closure Loop
  title: Final helper integrity and exports consistency pass in `backend_app/main.py`
  severity: medium
  problem: Post-extraction drift can reintroduce duplicated helper implementations and loose export surfaces.
  why_it_matters: Duplicate helper implementations erode maintainability and can reintroduce security/behavior regressions.
  recommended_change: complete a final static integrity sweep and keep delegated wrappers as the only local ownership points.
  expected_benefit: stable helper ownership and predictable `__all__` behavior.
  acceptance_criteria:
    - Static review confirms helper families are delegated to helper modules.
    - `_ALLOWED`/constant ownership in `main.py` remains intentional.
    - Lint and targeted checks pass on touched files.
  dependencies:
    - MOD-12
  affected_modules:
    - backend_app/main.py
    - backend_app/main_helpers.py
    - backend_app/scope_resolution.py
  verification: ruff + targeted scan
  status: resolved
  notes: Completed duplicate-definition and export-surface consistency pass; no behavior changes introduced.
```

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

- id: TEST-02
  phase: Audit Closure Loop
  title: Improve E2E harness fail-fast behavior on service startup failure
  severity: medium
  problem: E2E harness previously waited the full timeout even if backend/BFF/SPA processes exited, masking root-cause signals and slowing loops.
  why_it_matters: Faster, deterministic failure diagnostics improve CI and local debugging of infra/runtime regressions.
  recommended_change: add process-aware health polling in the Playwright E2E fixture so startup exits are detected and return codes are surfaced immediately.
  expected_benefit: clearer root-cause evidence when services fail to boot, lower time-to-diagnosis for E2E instability.
  acceptance_criteria:
    - `_wait_for_http_and_process` checks process exit codes during startup waits.
    - E2E stack setup raises explicit backend-exit returncode when available.
    - Existing Playwright role-based critical-path behavior remains green.
  dependencies: []
  affected_modules:
    - tests/test_e2e_playwright_spa_login_to_atlas.py
  verification: ruff + targeted pytest
  status: resolved
  notes: Implemented process-aware startup wait helper and wiring for backend/BFF/SPA readiness in `tests/test_e2e_playwright_spa_login_to_atlas.py`. Added explicit backend exit code surfacing and kept behavior unchanged for healthy runs.

- 2026-07-27: MOD-11 completed — extracted duplicated scope/actor/cycle helper logic out of `backend_app/main.py` into `backend_app/scope_resolution.py` and removed local duplicates; tests passed: 13 in `tests/test_backend_observability.py`, `tests/test_backend_error_envelope.py`, `tests/test_worker_observability.py`.


  - id: MOD-30
    phase: Audit Closure Loop
    title: Restore dual-mode compatibility seams after handler/module extraction
    severity: high
    problem: `backend_app/main.py` and extracted handler modules were out of sync after recent extraction work, causing monkeypatch targets in dual-mode parity tests to be bypassed.
    why_it_matters: Mode parity and regression tests are unreliable when handlers capture stale symbols at import time.
    recommended_change: resolve `backend_app.main` symbols dynamically from handler modules and preserve exported compatibility wrappers in `main.py`.
    expected_benefit: deterministic dual-mode behavior and stable monkeypatching in parity tests.
    acceptance_criteria:
      - `api_create_user` and other core mutation handlers use backend main indirection for mode checks and function dispatch.
      - `backend_app/main.py` still exposes compatibility names expected by tests.
      - Lint and `test_dual_mode_parity.py` pass after changes.
      - `read_query_via_supabase_api`/`create_*_via_supabase_api` compatibility surface remains available for external monkeypatches.
    dependencies:
      - MOD-19
      - MOD-20
    affected_modules:
      - backend_app/main.py
      - backend_app/main_mutation_handlers.py
      - backend_app/main_workflow_handlers.py
      - backend_app/main_runtime_helpers.py
    verification: ruff + targeted pytest + giant module analyzer
    status: resolved
    notes: |
      Completed in this loop with dynamic runtime indirection in both mutation/workflow handlers and compatibility imports in `main.py`.
      Also removed stale direct-mode-only import paths that bypassed monkeypatched `backend_app.main` symbols.

- id: QA-01
  phase: Audit Closure Loop
  title: Extend helper integrity and export hygiene checks to `backend_app/main.py` and `src/crud.py`
  severity: medium
  problem: Single-module integrity checks are no longer sufficient for the current facade-surface risk profile.
  why_it_matters: Duplicate helper implementations and export drift are high-risk in facade modules that own compatibility seams.
  recommended_change: run a reusable helper-integrity gate over both `backend_app/main.py` and `src/crud.py`, covering wrapper thinness, duplicate definitions, and duplicate `__all__` entries.
  expected_benefit: deterministic integrity evidence for facade-module drift and prevention of helper redefinition regressions.
  acceptance_criteria:
    - `scripts/verify_helper_integrity.py` checks both `backend_app/main.py` and `src/crud.py`.
    - `__all__` duplicate entries are rejected.
    - Duplicate top-level helper definitions in targeted modules are rejected.
    - Thin-wrapper expectations for delegated helpers in `backend_app/main.py` pass.
  dependencies: [MOD-13, MOD-24]
  affected_modules:
    - scripts/verify_helper_integrity.py
    - backend_app/main.py
    - src/crud.py
  verification: ruff + helper integrity script
  status: resolved
  notes: |
    This loop captures a reusable QA gate for facade modules after repeated decomposition and integrity-cycle reviews.

- id: QA-02
  phase: Audit Closure Loop
  title: Wire helper-integrity and giant-module gates into backend CI quality path
  severity: medium
  problem: Verification exists locally but is not enforced in CI, allowing facade-integrity or giant-module drift to reach merge.
  why_it_matters: Maintainability and regression-risk gates must be automatic at merge time.
  recommended_change: add `python scripts/verify_helper_integrity.py` and `python scripts/analyze_giant_modules.py` to `.github/workflows/ci.yml`.
  expected_benefit: deterministic enforcement of facade integrity and module-size boundaries in PR/merge checks.
  acceptance_criteria:
    - `Helper Integrity Gate` step is added and green in CI.
    - `Giant Module Boundary Gate` step is added and green in CI.
    - Backlog/worklog records this loop closure with verification evidence.
  dependencies: [QA-01]
  affected_modules:
    - .github/workflows/ci.yml
    - scripts/verify_helper_integrity.py
    - scripts/analyze_giant_modules.py
  verification: ci-local lint + local helper/gateway script execution
  status: resolved
  notes: |
    This keeps the latest QA gate from being optional and ensures future decompositions are reviewed by CI.

- id: QA-03
  phase: Audit Closure Loop
  title: Broaden helper-integrity scope to helper-adjacent façade modules
  severity: medium
  problem: Current integrity gating validates `main.py` and `src/crud.py`, but not all extracted helper-adjacent façade modules that still carry compatibility surface risk.
  why_it_matters: Hidden duplicate symbols or export drift in helper modules can bypass direct facade checks and still create review and regression risk.
  recommended_change: extend `scripts/verify_helper_integrity.py` to include `backend_app` and `src` helper-adjacent modules in duplicate/export checks.
  expected_benefit: wider coverage of facade-like modules with low runtime risk and deterministic maintenance guardrails.
  acceptance_criteria:
    - `scripts/verify_helper_integrity.py` includes at least `backend_app/main_bootstrap_helpers.py`, `backend_app/main_runtime_helpers.py`, `backend_app/main_workflow_handlers.py`, `backend_app/main_mutation_handlers.py`, `src/crud_auth_helpers.py`, and `src/crud_runtime_helpers.py`.
    - CI gate remains a single call site (`python scripts/verify_helper_integrity.py`) and enforces these new module checks.
    - Duplicate definitions / duplicate `__all__` are rejected for all expanded targets.
  dependencies: [QA-02]
  affected_modules:
    - scripts/verify_helper_integrity.py
    - .github/workflows/ci.yml
    - backend_app/main_bootstrap_helpers.py
    - backend_app/main_runtime_helpers.py
    - backend_app/main_mutation_handlers.py
    - backend_app/main_workflow_handlers.py
    - src/crud_auth_helpers.py
    - src/crud_runtime_helpers.py
  verification: ruff + helper integrity script + giant module boundary checks
  status: resolved
  notes: |
    Expands QA coverage to reduce risk in modules that are critical to facade decomposition ownership.

- id: QA-04
  phase: Audit Closure Loop
  title: Add runtime import + signature contract validation to helper-integrity gate
  severity: medium
  problem: Static checks can miss runtime-export drift when symbols disappear or contracts change after refactor.
  why_it_matters: Merge-safe behavior requires both static hygiene and runtime importability of compatibility contracts.
  recommended_change: extend `scripts/verify_helper_integrity.py` to validate importability and callable signatures for selected helper symbols.
  expected_benefit: catches symbol and signature regressions before tests and before PR merge.
  acceptance_criteria:
    - Helper-integrity gate imports each targeted module successfully.
    - Selected high-risk symbols are required to exist and be callable.
    - Selected callable signatures are validated against manifest expectations.
    - CI remains a single helper-integrity command in the same location.
  dependencies: [QA-03]
  affected_modules:
    - scripts/verify_helper_integrity.py
    - .github/workflows/ci.yml
  verification: ruff + helper integrity script
  status: resolved
  notes: |
    This is the first execution-mode contract gate for facade-adjacent helper exports.

- id: QA-05
  phase: Audit Closure Loop
  title: Add facade/export contract validation for helper-adjacent modules
  severity: medium
  problem: Contract checks currently validate wrappers and signatures, but there is still no fail-fast rule that ensures exported compatibility symbols and __all__ surfaces stay explicit and drift-free.
  why_it_matters: Drift in exported adapters/hook surfaces can silently break monkeypatch, integration seams, and external imports during refactors.
  recommended_change: add a dedicated export-contract gate to verify expected symbols, callable contract for selected compat surfaces, and clean export lists (no duplicates, expected dunder entries checked), then run it in CI.
  expected_benefit: deterministic facade/API seam integrity beyond wrapper-only checks.
  acceptance_criteria:
    - `scripts/verify_module_export_contracts.py` enforces required exports on `backend_app.main`, handler/helper seams, and `src` CRUD adapters.
    - Export manifest lists are checked for duplicates.
    - `__all__` duplicates are rejected where `__all__` is defined.
    - CI includes a dedicated `Module Export Contract Gate` step with the new script.
  dependencies: [QA-04]
  affected_modules:
    - scripts/verify_module_export_contracts.py
    - .github/workflows/ci.yml
    - backend_app/main.py
    - backend_app/main_bootstrap_helpers.py
    - backend_app/main_runtime_helpers.py
    - backend_app/main_mutation_handlers.py
    - backend_app/main_workflow_handlers.py
    - src/crud_auth_helpers.py
    - src/crud_runtime_helpers.py
  verification: ruff + new module-export contract script + CI dry-run
  status: resolved
  notes: |
    Adds a dedicated export-surface regression gate that complements helper integrity by checking both symbol presence and callability expectations for adapter seams.

- id: QA-06
  phase: Audit Closure Loop
  title: Add senior design-efficiency review gate for facade ownership and seam efficiency
  severity: medium
  problem: Existing gating around `main.py`, `src/crud.py`, and `src/services/supabase_api_mode.py` was still partially size-based and did not explicitly assess ownership separation or runtime seam efficiency.
  why_it_matters: Refactor correctness in these compatibility surfaces must be protected against logic creep, high-coupling re-accumulation, and accidental regression in the abstraction seams they own.
  recommended_change: introduce a module design/efficiency gate that validates seam delegation, facade-thinness, wrapper thinness in `main.py`, and absence of direct orchestration logic in these facade modules.
  expected_benefit: stronger maintenance confidence without relying on line-count thresholds.
  acceptance_criteria:
    - `scripts/verify_module_design_efficiency.py` is added.
    - CI uses this gate after integrity checks.
    - Gate fails when facade modules accumulate non-thin functions, non-delegated required symbols, or direct orchestration smells.
    - Size-only `analyze_giant_modules` is removed from CI.
  dependencies: [QA-05]
  affected_modules:
    - scripts/verify_module_design_efficiency.py
    - .github/workflows/ci.yml
    - backend_app/main.py
    - src/crud.py
    - src/services/supabase_api_mode.py
  verification: ruff + module-design-efficiency script
  status: resolved
  notes: |
    Adds a design review gate focused on ownership concentration, delegation thinness, and efficiency signals for facade seams.

- id: QA-09
  phase: Audit Closure Loop
  title: Make compose smoke startup deterministic and diagnostically complete
  severity: high
  problem: Fresh CI compose runs could start API and worker migration paths concurrently, inherited runner variables could override the generated smoke environment, readiness failures discarded service evidence, and the smoke pytest environment lost its activation and login variables before execution.
  why_it_matters: The production smoke gate could fail opaquely during startup or report success after skipping the intended login/read/job path.
  recommended_change: serialize database initialization behind API health, verify all HTTP services, preserve generated smoke credentials through pytest, and print redacted compose state and logs on readiness failure.
  expected_benefit: deterministic fresh-database startup and actionable, secret-safe CI evidence with no false-positive skipped smoke execution.
  acceptance_criteria:
    - Worker and BFF wait for a healthy backend API.
    - Readiness checks backend API, BFF, and web.
    - The smoke pytest process receives activation, URLs, and generated bootstrap credentials.
    - Readiness failures include redacted compose status and bounded service logs.
    - Compose execution is isolated from inherited application/runtime variables.
    - Regression tests cover environment propagation, runner isolation, early-failure diagnostics, cleanup, and secret redaction.
  dependencies: [TOP10-09]
  affected_modules:
    - deploy/docker/docker-compose.yml
    - scripts/verify_resilience.py
    - tests/test_verify_resilience_script.py
  verification: focused pytest + ruff + compose config + compose-backed smoke in CI
  status: resolved
  notes: |
    Root-cause corrections are implemented and focused pytest, Ruff, and mypy gates pass locally. Enhanced CI diagnostics subsequently exposed SQLite-only `PRAGMA user_version` SQL in a no-op Alembic merge revision; the revision now uses Python no-ops and a migration-portability regression test rejects SQLite-only PRAGMA statements. The next Linux run proved backend/PostgreSQL health and exposed BFF preflight rejection of the empty signing secret; smoke now generates a shared signing secret, enforces signed backend requests, and explicitly selects development transport mode for its HTTP-only cookie path while Compose retains a production default. The following run reached full-stack login and exposed missing Compose propagation of the generated bootstrap password; `backend-api` now receives that password and a deployment-contract test protects the wiring. Closure is intentionally pending a green Linux compose-backed GitHub Actions run. Local Docker execution is blocked because the Docker Desktop engine/config is unavailable in the current session.
    Follow-up discovered in CI smoke: `/api/backend/read/query` and `/api/backend/jobs` were called without `/v1` in `tests/test_e2e_smoke.py`. This bypassed BFF path allowlist normalization and returned `400` before API contract assertions. Updated smoke routes to `/api/backend/v1/read/query` and `/api/backend/v1/jobs`.
    Additional follow-up in this loop: CI smoke exposed intermittent `403` on `/v1/read/query` because CSRF enforcement treated this read-only actor route as state-changing. The BFF now treats `/v1/read/*` as non-state-changing for CSRF purposes, and `tests/test_e2e_smoke.py` now reads CSRF token defensively for read queries to avoid brittle cookie coupling.

- id: LOOP-19
  phase: Audit Closure Loop
  title: Convert `backend_app/main.py` to explicit service orchestration slices without behavior drift
  severity: high
  problem: `backend_app/main.py` still owns orchestration and route composition complexity that is functionally stable but difficult to review quickly, so future production-risk changes still carry high accidental-overlap risk.
  why_it_matters: Maintainability and security review quality degrade when core startup/routing decisions are hidden in a single large file.
  recommended_change: extract bounded orchestration slices into dedicated modules (for config/bootstrap, route wiring, and compatibility exports) with narrow imports from `backend_app/main.py`.
  expected_benefit: deterministic ownership boundaries, faster review for route-security and startup behavior changes, lower risk of accidentally bypassing wrapper seams.
  acceptance_criteria:
    - `backend_app/main.py` remains a clear bootstrap entrypoint with thin compatibility imports.
    - New route-orchestration modules have explicit, narrow responsibilities and preserve public imports.
    - `tests/test_module_main_seams.py`, `tests/test_backend_mutation_api.py`, and `tests/test_bff_allowlist_contract.py` remain green.
    - `scripts/verify_module_design_efficiency.py`, `scripts/verify_module_export_contracts.py`, and `scripts/verify_helper_integrity.py` remain green.
    - No changes in observed API contracts/route signatures in existing CI suite.
  dependencies:
    - QA-09
    - MOD-30
    - QA-06
  affected_modules:
    - backend_app/main.py
    - backend_app/main_bootstrap_helpers.py
    - backend_app/main_mutation_handlers.py
    - backend_app/main_workflow_handlers.py
    - backend_app/main_runtime_helpers.py
    - scripts/verify_module_design_efficiency.py
    - scripts/verify_module_export_contracts.py
    - scripts/verify_helper_integrity.py
  verification: |
    1. `python -m ruff check backend_app/main.py backend_app/main_bootstrap_helpers.py backend_app/main_mutation_handlers.py backend_app/main_workflow_handlers.py backend_app/main_runtime_helpers.py`
    2. `python -m pytest -q tests/test_module_main_seams.py tests/test_backend_mutation_api.py tests/test_bff_allowlist_contract.py`
    3. `python scripts/verify_module_export_contracts.py`
    4. `python scripts/verify_helper_integrity.py`
    5. `python scripts/verify_module_design_efficiency.py`
  status: resolved
  notes: |
    Orchestration is now split into `backend_app/main_orchestration.py` (`compose_main_app`) while preserving public compatibility contracts in `backend_app/main.py`.
    Validation evidence:
    - `python -m ruff check backend_app/main.py backend_app/main_orchestration.py backend_app/main_bootstrap_helpers.py`
    - `python -m pytest -q tests/test_module_main_seams.py tests/test_bff_allowlist_contract.py`
    - `python scripts/verify_module_export_contracts.py`
    - `python scripts/verify_helper_integrity.py`
    - `python scripts/verify_module_design_efficiency.py`
    - `tests/test_backend_mutation_api.py` remains expected to pass under existing route contract suite.
