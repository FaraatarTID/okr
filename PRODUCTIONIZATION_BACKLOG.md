# Productionization Backlog (Structured)

This backlog is derived from `docs/PRODUCTIONIZATION_AUDIT.md` and current repository state.

## 2026-07-26

### ID: CFG-01
- Title: Normalize production-mode signal across backend and BFF
- Severity: Medium
- Category: Configuration
- Description: Production behavior should be consistently detected across backend and BFF using aligned env aliases.
- Acceptance Criteria:
  - Backend and BFF read the same production signal sources.
  - Regression tests cover alias combinations.
- Dependencies: None
- Estimated Scope: Small
- Affected Files:
  - `backend_app/config.py`
  - `spa-bff/src/config.ts`
  - `tests/test_backend_config_validation.py`
  - `spa-bff/test/config.test.ts`
- Status: Completed

### ID: TYPE-01
- Title: Reduce repo mypy debt for broader type-checking readiness
- Severity: Medium
- Category: Quality
- Description: The repository has broad static typing debt, primarily from legacy SQLAlchemy unions, optional handling in runtime paths, and helper contracts not yet normalized.
- Acceptance Criteria:
  - Large mypy pass against `src/` and `backend_app/` reports only issues justified by tracked exceptions.
  - New refactor changes do not introduce additional mypy regressions.
  - Verification command and evidence are updated in the work log.
- Dependencies: None
- Estimated Scope: Large
- Affected Files:
  - `src/*`
  - `backend_app/*`
- Status: In Progress

### ID: AUTH-01
- Title: Ensure mutation-route matrix remains complete as API evolves
- Severity: High
- Category: Security
- Description: New mutation routes must be captured by authorization matrix and regression tests.
- Acceptance Criteria:
  - Mutation endpoint discovery and matrix coverage tests run in CI.
  - No known mutation route is missing from the matrix.
- Dependencies: `tests/test_backend_mutation_api.py`
- Estimated Scope: Small
- Affected Files:
  - `tests/test_backend_mutation_auth_matrix.py`
- Status: Completed

### ID: NET-01
- Title: Enforce backend-private topology in deploy-time policy
- Severity: Critical
- Category: Security
- Description: Prevent runtime deployment from pointing backend API traffic at public endpoints.
- Acceptance Criteria:
  - Deployment config checks reject public backend targets in runtime mode.
  - Tests cover public DNS and public IP rejection paths.
- Dependencies: None
- Estimated Scope: Small
- Affected Files:
  - `scripts/check_deploy_config.py`
  - `tests/test_check_deploy_config_script.py`
- Status: Completed

### ID: ARCH-01
- Title: Fail-fast production configuration validation
- Severity: Critical
- Category: Security / Reliability
- Description: Startup/CI must block weak service token, missing signing secret, insecure cookie config, and other production-hardening gaps.
- Acceptance Criteria:
  - A dedicated validation function exists and runs in production.
- Dependencies: `CFG-01`, `NET-01`
- Estimated Scope: Medium
- Affected Files:
  - `backend_app/config.py`
  - `spa-bff/src/config.ts`
  - `scripts/check_deploy_config.py`
  - Validation test files
- Status: Completed

### ID: ARCH-02
- Title: Split timer/job operations into dedicated backend router module
- Severity: High
- Category: Maintainability
- Description: Move operation handlers out of monolithic `backend_app/main.py` into `backend_app/routers/operations_routes.py` without contract changes.
- Acceptance Criteria:
  - `backend_app/main.py` does not define the operation endpoints directly.
- Dependencies: `ARCH-01`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/operations_routes.py`
- Status: Completed

### ID: ARCH-03
- Title: Decompose `backend_app/main.py` into domain router modules
- Severity: High
- Category: Architecture
- Description: Remaining route groups should be extracted into domain-specific routers while preserving API behavior and tests.
- Acceptance Criteria:
  - New router modules own route registration by domain.
- Dependencies: `ARCH-02`
- Estimated Scope: Large
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/*.py`
- Status: Completed
- Notes:
   - `/v1/nodes/*` routes extracted to `backend_app/routers/node_mutation_routes.py`.
   - `/v1/users/*` routes extracted to `backend_app/routers/user_mutation_routes.py`.
   - `/v1/check-ins` route extracted to `backend_app/routers/checkin_mutation_routes.py`.
   - `/v1/cycles/*` routes extracted to `backend_app/routers/cycle_mutation_routes.py`.
   - `/v1/teams/*` routes extracted to `backend_app/routers/team_mutation_routes.py`.
   - `/v1/experiments/*` routes extracted to `backend_app/routers/experiment_mutation_routes.py`.
   - Retrospective, alignment, and work-log mutation routes extracted to `backend_app/routers/analytics_mutation_routes.py`.

### ID: ARCH-03g
- Title: Split retrospective/alignment/work-log mutation routes into dedicated backend router module
- Severity: High
- Category: Architecture
- Description: Move remaining mutation registration blocks (`/v1/retrospectives`, `/v1/weekly-plans`, `/v1/alignments`, `/v1/objective-alignment-links`, `/v1/work-logs`) out of `main.py`.
- Acceptance Criteria:
  - All remaining mutation route decorators are removed from `main.py`.
  - Behavior remains unchanged through handler delegation.
- Dependencies: `ARCH-03f`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/analytics_mutation_routes.py`
- Status: Completed

### ID: ARCH-03b
- Title: Split user mutation routes into dedicated backend router module
- Severity: High
- Category: Architecture
- Description: `/v1/users` and `/v1/users/{user_id}/reset-password` routes should be owned by a domain router while preserving handler behavior in `main.py`.
- Acceptance Criteria:
  - Route decorators for user mutation endpoints are moved out of `backend_app/main.py` into `backend_app/routers/user_mutation_routes.py`.
  - Core handler functions remain in `main.py`.
  - Mutation API and matrix tests remain green.
- Dependencies: `ARCH-03a`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/user_mutation_routes.py`
- Status: Completed

### ID: ARCH-03c
- Title: Split check-in mutation route into dedicated backend router module
- Severity: High
- Category: Architecture
- Description: Move the `/v1/check-ins` route registration out of `backend_app/main.py` while preserving validation and mutation behavior.
- Acceptance Criteria:
  - `@app.post("/v1/check-ins")` decorator is removed from the core handler.
  - Route is registered via `backend_app/routers/checkin_mutation_routes.py`.
  - Full mutation API and route-matrix tests pass.
- Dependencies: `ARCH-03b`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/checkin_mutation_routes.py`
- Status: Completed

### ID: ARCH-03d
- Title: Split cycle mutation routes into dedicated backend router module
- Severity: High
- Category: Architecture
- Description: Move `/v1/cycles/*` route registration out of `main.py` and into a dedicated router module.
- Acceptance Criteria:
  - Cycle route decorators are removed from `main.py` and reintroduced via router registration.
  - Core handlers stay unchanged in `main.py`.
- Dependencies: `ARCH-03c`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/cycle_mutation_routes.py`
- Status: Completed

### ID: ARCH-03e
- Title: Split team mutation routes into dedicated backend router module
- Severity: High
- Category: Architecture
- Description: Move `/v1/teams/*` route registration out of `main.py` and into a dedicated router module.
- Acceptance Criteria:
  - Team create/update/delete routes are registered through `team_mutation_routes`.
- Dependencies: `ARCH-03d`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/team_mutation_routes.py`
- Status: Completed

### ID: ARCH-03f
- Title: Split experiment mutation routes into dedicated backend router module
- Severity: High
- Category: Architecture
- Description: Move `/v1/experiments/*` route registration out of `main.py` into `experiment_mutation_routes`.
- Acceptance Criteria:
  - `@app.post("/v1/experiments")`, `@app.patch("/v1/experiments/{experiment_id}")`, and `@app.post("/v1/experiments/{experiment_id}/close")` are removed from `main.py`.
- Dependencies: `ARCH-03e`
- Estimated Scope: Small
- Affected Files:
  - `backend_app/main.py`
  - `backend_app/routers/experiment_mutation_routes.py`
- Status: Completed

### ID: ARCH-04
- Title: Extract domain services from oversized CRUD facade
- Severity: High
- Category: Architecture
- Description: Move orchestration and authorization checks from `src/crud.py` facade to domain services.
- Acceptance Criteria:
- `src/crud.py` is reduced and domain boundaries are explicit.
  - New service modules enforce actor/authorization consistently.
- Dependencies: `ARCH-03`
- Estimated Scope: Large
- Affected Files:
  - `src/crud.py`
  - `src/domain/*.py`
  - `backend_app/main.py`
- Status: Completed
- Notes:
  - AUTH extraction slice completed for auth/proxy orchestration (`src/domain/auth_service.py`) and consumer delegation.
  - READ orchestration slice completed for dashboard/goal/query helpers and cycle/team/retro/experiment/caretaker user entrypoints via `src/domain/read_service.py`.
  - Remaining internal dead helper `_get_latest_checkins_by_kr` in `src/crud.py` removed.

### ID: OBS-01
- Title: Establish production observability baseline
- Severity: Medium
- Category: Reliability
- Description: Standardize logging, metrics, and alerting contracts for API/worker/DB/provider paths.
- Acceptance Criteria:
  - JSON logging, correlation IDs, and key metrics are in place with owned dashboards.
- Dependencies: None
- Estimated Scope: Medium
- Affected Files:
  - API/BFF/worker configuration and instrumentation
- Status: TODO

### ID: PERF-01
- Title: Add performance/query budgets for expensive endpoints
- Severity: Medium
- Category: Scalability
- Description: Add budgeted tests for Atlas snapshot, leadership metrics, audit summary, and job polling paths.
- Acceptance Criteria:
- Budget tests and baseline values committed.
  - CI enforces budget thresholds.
- Dependencies: `ARCH-03`
- Estimated Scope: Medium
- Affected Files:
  - Domain/service query modules
  - Performance test suite
- Status: TODO

### ID: JOB-01
- Title: Harden async worker queue behavior
- Severity: Medium
- Category: Reliability
- Description: Add deterministic lease/retry/dead-letter/alert behavior for async job execution and restart scenarios.
- Acceptance Criteria:
  - Explicit worker restart idempotency and dead-letter paths are tested.
- Dependencies: `ARCH-04`
- Estimated Scope: Medium
- Affected Files:
  - `backend_worker`
  - `backend_app/jobs.py`
- Status: TODO

### ID: AI-01
- Title: Define and enforce AI/PII governance and prompt policy
- Severity: Medium
- Category: Security
- Description: Add data-classification and prompt/output handling controls around AI providers.
- Acceptance Criteria:
  - Prompt minimization and provider governance policy are encoded and tested.
- Dependencies: `ARCH-01`
- Estimated Scope: Medium
- Affected Files:
  - `src/services/ai_service.py`
  - `src/services/ai_provider.py`
- Status: TODO

### ID: ENV-01
- Title: Align local and production DB parity
- Severity: Medium
- Category: Reliability
- Description: Make Postgres the default local integration path; keep SQLite only for unit-only scenarios.
- Acceptance Criteria:
  - CI and local docs/compose show canonical Postgres path by default.
- Dependencies: None
- Estimated Scope: Medium
- Affected Files:
  - `docker-compose*.yml`
  - Local setup docs
  - Test harness scripts
- Status: TODO
