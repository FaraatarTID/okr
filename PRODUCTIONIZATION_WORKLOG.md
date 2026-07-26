# Productionization Work Log

## 2026-07-26

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade
Status: **Completed**

- Rationale:
  - The `src.crud` facade still mixed read/query orchestration and auth/proxy branching with persistence orchestration across too many direct helper calls.
- Root cause:
  - Read/query orchestration had been split partially, leaving lingering facade-level responsibilities and a dead utility helper.
- Impact map:
  - Files: `src/crud.py`, `src/domain/read_service.py`, `src/domain/auth_service.py`
  - Functions: read/query wrappers for dashboard/goals/user/team/cycle/experiment/retrospective/work-log paths plus user reads and auth proxy helpers.
- Implementation:
  - Completed the final user-read delegation slice in `src/domain/read_service.py` and rewired `src/crud.py` to delegate.
  - Removed the unused `_get_latest_checkins_by_kr` helper from `src/crud.py` after confirming there were no remaining call sites.
- Files changed:
  - `src/crud.py`
  - `src/domain/read_service.py`
  - `src/domain/auth_service.py`
- Acceptance verification:
  - Confirmed read/query delegation coverage and removed dead helper; no behavior change expected in call paths.
- Verification:
  - `ruff format src/crud.py src/domain/read_service.py src/domain/auth_service.py`
  - `ruff check src/crud.py src/domain/read_service.py src/domain/auth_service.py`
  - `python -m pytest -q tests/test_crud_ownership_and_timer.py tests/test_performance_hotpaths.py tests/test_auth_rate_limit.py`
- Result:
  - `ruff` passes.
  - `22 passed` on selected fast-path suite.

### Issue: ARCH-03 — Decompose `backend_app/main.py` into domain router modules
Status: **In Progress**

- Rationale:
  - AI endpoints were extracted into `backend_app/routers/ai_routes.py`, which is consistent with modularization goals but broke monkeypatch-based contract tests that patch helper symbols on `backend_app.main`.
- Root cause:
  - The refactor moved route handlers away from `main.py` without preserving public module seams (`analyze_node`, `analyze_team_health`, `calculate_burnout_risk`, `generate_predictive_outlook`, `detect_strategy_gaps`) previously relied on by existing tests and potential integrations.
- Files changed:
  - `backend_app/main.py` (added AI helper compatibility exports into module namespace)
  - `backend_app/routers/ai_routes.py` (AI route handlers remain routed through module namespace in `register_ai_routes`)
- Acceptance verification:
  - AI and timer/job test paths that previously regressed now pass with router extraction intact.
- Tests run:
  - `python -m ruff format backend_app/main.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/ai_routes.py backend_app/routers/operations_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py -k "timer or jobs or ai"`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"`
- Result:
  - `ruff` checks pass.
  - `24 passed` from `timer or jobs or ai` group.
  - `1 passed` from mutation matrix completeness gate.

### Issue: ARCH-03a — Split node mutation handlers into router module
Status: **Completed**

- Rationale:
  - Remaining large mutation block in `backend_app/main.py` mixed handler responsibilities and made route modularization difficult.
- Root cause:
  - Node handlers were still defined directly on the main app, preventing full domain-router decomposition.
- Implementation:
  - Created `backend_app/routers/node_mutation_routes.py` with `register_node_mutation_routes(...)`.
  - Moved route registration for `/v1/nodes/*` into that router.
  - Kept actual handler implementations (`api_create_goal`, `api_create_objective`, `api_create_key_result`, `api_create_task`, `api_update_node`, `api_delete_node`) in `backend_app/main.py` for behavior stability.
  - Updated `main.py` to wire the new router and removed `@app.*` decorators from the node handlers.
- Acceptance verification:
  - Preserved handler behavior and public contract through wrapper endpoints and unchanged core logic.
  - Maintained compatibility with existing monkeypatch-centric tests that still patch module functions on `backend_app.main`.
- Files changed:
  - `backend_app/routers/node_mutation_routes.py` (added)
  - `backend_app/main.py` (router import/wiring, removal of `@app` node decorators)
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/node_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/ai_routes.py backend_app/routers/operations_routes.py backend_app/routers/node_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py -k "nodes"` -> `33 passed`
  - `python -m pytest -q tests/test_backend_mutation_api.py -k "timer or jobs or ai"` -> `24 passed`
  - `python -m pytest -q tests/test_backend_mutation_api.py -k "not nodes"` -> `82 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03b — Split user mutation routes into router module
Status: **Completed**

- Rationale:
  - User mutation handlers were still bound directly on `app` and outside the domain router path used by the modularization plan.
- Root cause:
  - Remaining `/v1/users` mutation decorators in `main.py` mixed route registration and core request handling.
- Files changed:
  - `backend_app/main.py` (added user mutation router registration and kept core handlers as plain functions)
  - `backend_app/routers/user_mutation_routes.py` (new wrapper router for `/v1/users*` mutation endpoints)
- Acceptance verification:
  - User route behavior preserved through delegation to existing handler functions.
  - Router extraction did not change response status codes or permissions.
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/user_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/node_mutation_routes.py backend_app/routers/user_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03c — Split check-in mutation route into router module
Status: **Completed**

- Rationale:
  - The check-in mutation route was still declared directly on `app`, contrary to the decomposition direction.
- Root cause:
  - Remaining `/v1/check-ins` decorator kept handler registration co-located with core logic.
- Files changed:
  - `backend_app/main.py` (removed direct app decorator and added check-in router registration)
  - `backend_app/routers/checkin_mutation_routes.py` (new lightweight wrapper route module)
- Acceptance verification:
  - Preserved comment/risk validation and status/response behavior by delegating directly to existing core handler.
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/checkin_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/node_mutation_routes.py backend_app/routers/user_mutation_routes.py backend_app/routers/checkin_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03d — Split cycle mutation routes into router module
Status: **Completed**

- Rationale:
  - Cycle route handlers were still attached to `app` and bypassing the modular router decomposition.
- Root cause:
  - `/v1/cycles/*` endpoints remained in the monolithic route section.
- Files changed:
  - `backend_app/main.py` (added cycle router registration and removed direct route decorators)
  - `backend_app/routers/cycle_mutation_routes.py` (new route wrappers)
- Acceptance verification:
  - Route signatures, permissions, and behavior preserved through direct delegation.
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/cycle_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/node_mutation_routes.py backend_app/routers/user_mutation_routes.py backend_app/routers/checkin_mutation_routes.py backend_app/routers/cycle_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03e — Split team mutation routes into router module
Status: **Completed**

- Rationale:
  - Team mutation endpoints remained directly registered in `main.py`, delaying full router decomposition.
- Root cause:
  - The `/v1/teams/*` registration block had not yet been modularized after node/user/check-in/cycle extraction.
- Files changed:
  - `backend_app/main.py` (added team router registration and removed app decorators)
  - `backend_app/routers/team_mutation_routes.py` (new route wrappers)
- Acceptance verification:
  - Route semantics, payload mapping, and auth constraints preserved by delegating to existing handler functions.
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/team_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/node_mutation_routes.py backend_app/routers/user_mutation_routes.py backend_app/routers/checkin_mutation_routes.py backend_app/routers/cycle_mutation_routes.py backend_app/routers/team_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03f — Split experiment mutation routes into router module
Status: **Completed**

- Rationale:
  - Experiment mutation route decorators were still present in `main.py`.
- Root cause:
  - Route registration for `/v1/experiments*` had not yet followed node/user/check-in/cycle/team migration.
- Files changed:
  - `backend_app/main.py` (added experiment router registration and removed direct experiment decorators)
  - `backend_app/routers/experiment_mutation_routes.py` (new wrapper route module)
- Acceptance verification:
  - Idempotency-aware paths and authorization metadata preserved by delegating directly to existing handlers.
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/experiment_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/node_mutation_routes.py backend_app/routers/user_mutation_routes.py backend_app/routers/checkin_mutation_routes.py backend_app/routers/cycle_mutation_routes.py backend_app/routers/team_mutation_routes.py backend_app/routers/experiment_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03g — Split retrospective/alignment/work-log mutation routes into router module
Status: **Completed**

- Rationale:
  - The last remaining direct `@app` mutation route decorators in `main.py` covered retrospectives, weekly plans, alignments, and work-log deletion.
- Root cause:
  - Incomplete extraction of all mutation domain routes from `main.py`.
- Files changed:
  - `backend_app/main.py` (added analytics mutation router registration and removed remaining direct decorators)
  - `backend_app/routers/analytics_mutation_routes.py` (added route delegation module)
- Acceptance verification:
  - All extracted handlers retained exact signatures and response types by delegating to existing `main.py` handlers.
- Tests run:
  - `python -m ruff format backend_app/main.py backend_app/routers/analytics_mutation_routes.py`
  - `python -m ruff check backend_app/main.py backend_app/routers/node_mutation_routes.py backend_app/routers/user_mutation_routes.py backend_app/routers/checkin_mutation_routes.py backend_app/routers/cycle_mutation_routes.py backend_app/routers/team_mutation_routes.py backend_app/routers/experiment_mutation_routes.py backend_app/routers/analytics_mutation_routes.py`
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-03 — Decompose `backend_app/main.py` into domain router modules
Status: **Completed**

- Rationale:
  - `backend_app/main.py` still hosted all mutation route decorators, blocking modular ownership and future maintainability.
- Root cause:
  - Incremental route extraction had not yet been fully completed across all mutation families.
- Files changed:
  - `backend_app/main.py`
  - `backend_app/routers/*.py` (node, user, check-in, cycle, team, experiment, analytics router modules)
- Acceptance verification:
  - `rg` verification confirmed no remaining `@app.<method>` mutation decorators in `main.py`.
  - Mutation integration tests and route-matrix completeness test pass after final extraction.
- Tests run:
  - `python -m ruff format backend_app/main.py` -> formatted
  - `python -m ruff check` on all affected router modules -> passed
  - `python -m pytest -q tests/test_backend_mutation_api.py` -> `115 passed`
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes"` -> `1 passed`

### Issue: ARCH-02 — Split timer/job operations into dedicated backend router module
Status: **Completed**

- Rationale:
  - The previous refactor had `backend_app/main.py` still importing operation schemas and delegating to non-existent route definitions, creating a broken or incomplete modularization path.
- Root cause:
  - Operation handler code was partially moved out of `main.py` without a concrete router implementation; route registration references then pointed to missing symbols.
- Files changed:
  - `backend_app/routers/operations_routes.py` (added new router module)
  - `backend_app/main.py` (updated imports and router wiring)
- Acceptance verification:
  - Preserved external `/v1/timer/*` and `/v1/jobs/*` route contracts and auth behavior by delegating to existing `main.py` helpers.
- Tests run:
  - `python -m ruff format --check backend_app/main.py backend_app/routers/operations_routes.py` -> 2 files already formatted
  - `python -m ruff check backend_app/main.py backend_app/routers/operations_routes.py` -> all checks passed
  - `python -m pytest -q tests/test_backend_mutation_api.py -k "timer or jobs"` -> 7 passed, 108 deselected
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py -k "mutation_route_matrix_covers_all_v1_mutation_routes or test_timer"` -> 3 passed, 41 deselected
  - `python -m pytest -q tests/test_backend_private_ingress_enforcement.py -q` -> 4 passed
- Type check note:
  - `python -m mypy backend_app/routers/operations_routes.py backend_app/main.py` reports the pre-existing repository-wide baseline (`211 errors in 26 files`), not introduced by this router change.
- Known follow-up:
  - Continue backlog with highest remaining critical action from audit: endpoint authorization/matrix completeness and production configuration ingress hardening are already completed; next actionable high/medium item is modularizing remaining broad API modules and extracting domain service boundaries.

### Issue: CFG-01 — Normalize production-mode signal across backend and BFF
Status: **Completed**

- Rationale:
  - Production hardening gates were not consistently triggered because backend and BFF used different env aliases to detect production mode.
- Root cause:
  - Backend checked `OKR_ENV` then `OKR_RUNTIME_ENV`, while BFF checked only `OKR_RUNTIME_ENV`/`NODE_ENV`; `NODE_ENV` was unsupported by backend and `OKR_ENV` by BFF.
- Files changed:
  - `backend_app/config.py`
  - `spa-bff/src/config.ts`
- Tests added/updated:
  - `tests/test_backend_config_validation.py` (added production alias coverage for `NODE_ENV`)
  - `spa-bff/test/config.test.ts` (added production alias coverage for `OKR_ENV`)
- Verification:
  - `python -m pytest -q tests/test_backend_config_validation.py` -> 8 passed
  - `npm --prefix spa-bff test -- test/config.test.ts` -> 11 passed
  - `python -m pytest -q tests/test_backend_mutation_auth_matrix.py tests/test_spa_bff_deploy_policy.py tests/test_check_deploy_config_script.py tests/test_backend_request_signing.py::test_production_requires_distributed_security_state_backend` -> 64 passed
- Known follow-up:
  - Continue next highest-priority unresolved audit items, starting with route modularization for authorization safety.

#### Follow-up correction (applied)
- A follow-up correction was applied before handoff: production cookie-default logic keeps legacy non-development defaulting while still enforcing production signals via explicit `OKR_ENV`/`OKR_RUNTIME_ENV`/`NODE_ENV`.
- Updated verification:
  - `python -m ruff format --check backend_app/config.py tests/test_backend_config_validation.py` -> 2 files already formatted
  - `python -m ruff check backend_app/config.py tests/test_backend_config_validation.py tests/test_backend_mutation_auth_matrix.py` -> all checks passed
 - `python -m mypy backend_app/config.py` -> no issues
 - `npm --prefix spa-bff run build` -> success
 - `pytest -q tests/test_backend_config_validation.py tests/test_backend_mutation_auth_matrix.py tests/test_spa_bff_deploy_policy.py tests/test_check_deploy_config_script.py tests/test_backend_request_signing.py` -> 75 passed

### Issue: AUTH-01 — Ensure mutation-route matrix remains complete as API evolves
Status: **Completed**

- Rationale:
  - Existing matrix tests covered mutation behavior but did not fail when new mutation routes were added to `backend_app/main.py` without coverage.
- Root cause:
  - No automated drift check between route registration and mutation auth regression matrix.
- Files changed:
  - `tests/test_backend_mutation_auth_matrix.py`
- Implementation:
  - Added route-canonicalization and mutation-route completeness checks against all `POST/PUT/PATCH/DELETE` `/v1` routes in `backend_app.main`.
  - Added explicit allowlist entries for mutation routes validated by separate focused regression tests (AI/read/state/job timer cases).
  - Normalized `nodes` route patterns to avoid false drift for typed node-type endpoints.
- Tests added/updated:
  - `tests/test_backend_mutation_auth_matrix.py` (added `test_mutation_route_matrix_covers_all_v1_mutation_routes`, expanded allowlists/constants)
- Verification:
  - `python -m ruff format tests/test_backend_mutation_auth_matrix.py` -> 1 file reformatted
  - `python -m ruff format --check backend_app/config.py tests/test_backend_config_validation.py tests/test_backend_mutation_auth_matrix.py` -> 3 files already formatted
  - `python -m ruff check backend_app/config.py tests/test_backend_config_validation.py tests/test_backend_mutation_auth_matrix.py` -> all checks passed
  - `python -m mypy backend_app/config.py` -> no issues
  - `npm --prefix spa-bff run build` -> success
  - `npm --prefix spa-bff test -- test/config.test.ts` -> 11 passed
  - `pytest -q tests/test_backend_config_validation.py tests/test_backend_mutation_auth_matrix.py tests/test_spa_bff_deploy_policy.py tests/test_check_deploy_config_script.py tests/test_backend_request_signing.py` -> 76 passed

### Issue: NET-01 — Enforce backend-private topology in deploy-time policy

Status: **Completed**

- Rationale:
  - The codebase had checks for ports/binding and required flags, but no direct guard preventing an internal backend URL from being pointed at a public IP or public hostname.
- Root cause:
  - `scripts/check_deploy_config.py` did not validate `OKR_BACKEND_API_URL` as part of deployment hardening, so a mistaken value could still pass runtime checks.
- Files changed:
  - `scripts/check_deploy_config.py`
  - `tests/test_check_deploy_config_script.py`
- Implementation:
  - Added dedicated backend API URL validation in deployment checker:
    - requires http/https URL with hostname
    - validates private URL intent (rejects loopback/public hostnames in runtime mode)
    - validates IP addresses against RFC1918/link-local/private ranges
    - rejects obvious non-private DNS hostnames unless clearly internal/service-like
  - Added regression tests for:
    - public hostname rejection in runtime mode
    - public IP rejection in runtime mode
- Verification:
  - `python -m ruff format scripts/check_deploy_config.py`
  - `python -m ruff format --check scripts/check_deploy_config.py tests/test_check_deploy_config_script.py` -> both formatted
  - `python -m ruff check scripts/check_deploy_config.py tests/test_check_deploy_config_script.py` -> no issues
  - `python -m mypy scripts/check_deploy_config.py` -> no issues
  - `pytest -q tests/test_check_deploy_config_script.py` -> 15 passed

#### Known follow-up
- This check intentionally enforces strict internal-host patterns in `runtime` mode; teams running custom enterprise DNS naming should review with a one-time exception plan before hardening rollout.

### Issue: ARCH-01 — Add fail-fast production validation checks
Status: **Completed**

- Rationale:
  - The productionization checklist identifies startup-time security/config hardening as a critical control before risky production incidents.
- Root cause:
  - It was unclear whether fail-fast protections were complete across all paths.
- Files validated:
  - `backend_app/config.py` (startup validation of service token/signing/backend DB/security-state settings)
  - `spa-bff/src/config.ts` (startup validation and secure defaults)
  - `scripts/check_deploy_config.py` (environment validation gate)
  - `tests/test_backend_config_validation.py`
  - `tests/test_spa_bff_deploy_policy.py`
  - `tests/test_check_deploy_config_script.py`
  - `tests/test_backend_request_signing.py`
  - `tests/test_backend_mutation_auth_matrix.py`
- Verification:
  - `python -m pytest -q tests/test_backend_config_validation.py tests/test_spa_bff_deploy_policy.py tests/test_check_deploy_config_script.py tests/test_backend_request_signing.py::test_production_requires_distributed_security_state_backend` -> 31 passed

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade (AUTH slice)
Status: **In Progress**

- Rationale:
  - The `src.crud` facade still contained large orchestration and authorization logic, reducing domain boundary clarity.
- Root cause:
  - Authentication/user-facing delegation and authorization proxy behavior had been embedded directly in the compatibility layer.
- Impact map (slice completed):
  - Files: `src/crud.py`, `src/domain/auth_service.py`
  - Functions: auth/proxy helpers (`get_user_*`, `authenticate_user*`, `*authorize*`, throttling helpers)
  - Callers: auth and ownership checks used by CRUD helpers, route handlers, and tests that import `src.crud`
  - Config/tests: auth rate-limit and password bootstrap paths
- Changes:
  - Added `src/domain/auth_service.py` with extracted auth/orchestration helpers.
  - Rewired `src/crud.py` auth and backend-read proxy functions to delegate to the new domain service module.
- Risks introduced:
  - This is a slice of `ARCH-04`; remaining orchestration paths in `src.crud` still need extraction.
  - Potentially increased indirection for debug tracing and stack depth.
- Verification:
  - `ruff format src/crud.py src/domain/auth_service.py`
  - `ruff format --check src/crud.py src/domain/auth_service.py`
  - `ruff check src/crud.py src/domain/auth_service.py tests/test_auth_rate_limit.py tests/test_password_persistence.py`
  - `python -m pytest -q tests/test_auth_rate_limit.py tests/test_password_persistence.py` -> 20 passed
- Completion status:
  - Partially complete; `ARCH-04` remains open for remaining domain services.

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade (READ slice)
Status: **In Progress**

- Rationale:
  - Remaining backend-read proxy logic was still inlined across a large set of read-oriented `src.crud` functions, increasing coupling and making ownership boundaries hard to follow.
- Root cause:
  - The prior `AUTH` extraction slice did not move the generic read transport/orchestration branch set.
- Impact map:
  - Files: `src/crud.py`, `src/domain/read_service.py`, `src/domain/auth_service.py`
  - Functions: read wrappers for check-ins, experiments, cycles, nodes, team views, retrospectives, leadership, and weekly plans
  - Callers: dashboard, check-in, cycle, and reflection flows using stable `src.crud` read APIs
- Implementation:
  - Added `src/domain/read_service.py` with extracted backend-read proxy orchestration and fallback delegation.
  - Updated corresponding `src/crud.py` read wrappers to delegate directly to `read_service`.
  - Rewired helper `_backend_read_*` functions in `src/crud.py` to call `read_service` implementations.
- Verification:
  - `ruff format src/crud.py src/domain/auth_service.py src/domain/read_service.py`
  - `ruff check src/crud.py src/domain/auth_service.py src/domain/read_service.py tests/test_performance_hotpaths.py tests/test_crud_authorization.py`
  - `python -m pytest -q tests/test_performance_hotpaths.py tests/test_crud_authorization.py` -> `37 passed`
  - `python -m pytest -q tests/test_auth_rate_limit.py tests/test_password_persistence.py` -> `20 passed`
- Completion status:
  - `ARCH-04` still open for additional service slices, but the read/proxy orchestration slice is complete and passes targeted verification.

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade (READ query slice)
Status: **In Progress**

- Rationale:
  - `src/crud` still hosted additional query-style read orchestration that is better owned by a focused service module.
- Root cause:
  - Query-style reads were still coupled to helper modules directly from the facade, and read boundaries were still partial after the backend proxy slice.
- Files changed:
  - `src/domain/read_service.py` (added query delegation helpers)
  - `src/crud.py` (read wrappers now delegate to `read_service` for dashboard/goal tree/user goals/simple views and trend/goal-hour helpers)
- Implementation:
  - Added `get_user_goals_simple`, `get_dashboard_data`, `get_goal_tree`, `get_hours_by_goal`, and `get_daily_work_trend` delegates in `read_service`.
  - Rewired corresponding `src/crud.py` functions to call `read_service`.
- Verification:
  - `ruff format src/crud.py src/domain/read_service.py`
  - `ruff check src/crud.py src/domain/read_service.py`
  - `python -m pytest -q tests/test_crud_ownership_and_timer.py tests/test_performance_hotpaths.py tests/test_auth_rate_limit.py`
- Result:
  - `ruff` checks pass.
  - `22 passed` from selected fast-path tests.

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade (READ query slice 2)
Status: **In Progress**

- Rationale:
  - A second query-surface cleanup pass was needed for remaining `src.crud` direct read delegates.
- Root cause:
  - `get_node_by_external_id`, `get_user_data_from_sql`, and `get_sql_id_by_external` still bypassed the read service and kept facade-level read orchestration local.
- Files changed:
  - `src/domain/read_service.py` (added direct query delegation helpers)
  - `src/crud.py` (rewired these read wrappers to `read_service`)
- Verification:
  - `ruff format src/crud.py src/domain/read_service.py`
  - `ruff check src/crud.py src/domain/read_service.py`
  - `python -m pytest -q tests/test_crud_ownership_and_timer.py tests/test_performance_hotpaths.py tests/test_auth_rate_limit.py`
- Result:
  - `ruff` checks pass.
  - `22 passed` from selected fast-path tests.

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade (READ query slice 3)
Status: **In Progress**

- Rationale:
  - Read orchestration in `src.crud` was still present for check-in and KR-exp experiment queries.
- Root cause:
  - `get_check_ins` and `list_experiments_for_kr` were still bound directly to helper modules in the facade.
- Files changed:
  - `src/domain/read_service.py` (added remaining query read delegates)
  - `src/crud.py` (rewired these wrappers to `read_service`)
- Verification:
  - `ruff format src/crud.py src/domain/read_service.py`
  - `ruff check src/crud.py src/domain/read_service.py`
  - `python -m pytest -q tests/test_crud_ownership_and_timer.py tests/test_performance_hotpaths.py tests/test_auth_rate_limit.py`
- Result:
  - `ruff` checks pass.
  - `22 passed` from selected fast-path tests.

### Issue: ARCH-04 — Extract domain services from oversized CRUD facade (READ query slice 4)
Status: **In Progress**

- Rationale:
  - A final user-read facade pass was needed to complete small read orchestration cleanup.
- Root cause:
  - User read entrypoints (`get_user_by_username`, `get_user_by_id`, `get_all_users`, `get_team_members`) still delegated through `auth_service` directly in the facade.
- Files changed:
  - `src/domain/read_service.py` (added user-read delegation helpers)
  - `src/crud.py` (rewired user-read wrappers to `read_service`)
- Verification:
  - `ruff check src/crud.py src/domain/read_service.py`
  - `python -m pytest -q tests/test_crud_ownership_and_timer.py tests/test_performance_hotpaths.py tests/test_auth_rate_limit.py`
- Result:
  - `ruff` checks pass.
  - `22 passed` from selected fast-path tests.

### Issue: TYPE-01 — Reduce repo mypy debt for broader type-checking readiness
Status: **In Progress**

- Rationale:
  - Repository-wide static typing debt blocked reliable type-driven maintenance and CI hardening.
- Root cause:
  - SQLModel/SQLAlchemy typing, optional date math, and several legacy helper contracts are currently under-annotated for strict mode.
- Impact map (partial slice):
  - Files: `src/models.py`, `src/observability.py`, `src/services/http_client.py`, `src/services/pdf_service.py`, `src/services/backend_client.py`, `src/database.py`, `backend_app/security_state.py`, `src/crud_timer_helpers.py`, `src/crud_auth_helpers.py`, `src/utils/sync.py`
- Changes:
  - Added a typed SQLModel table base (`SQLModelTable`) to avoid `table=True` false-positive errors.
  - Added explicit typing for `ContextVar` usage and import ignore annotations for optional third-party typing.
  - Hardened payload/map typing in database backup export and removed datetime-time shadowing.
  - Removed duplicate `_app_state` dynamic initialization pattern in security state store.
  - Added Optional-safe datetime normalization around timer/auth math and owner-id coercion in sync payload import.
- Verification:
  - `ruff check src/models.py src/observability.py src/services/http_client.py src/services/pdf_service.py src/services/backend_client.py src/database.py backend_app/security_state.py src/crud_timer_helpers.py src/crud_auth_helpers.py src/utils/sync.py`
  - `python -m mypy --ignore-missing-imports --follow-imports=skip src backend_app`
- Result:
  - Mypy errors reduced from **130** to **82**.
  - Remaining blockers concentrated in:
    - `src/audit_queries.py`, `src/audit.py`
    - `src/domain/read_queries.py`, `src/domain/analytics.py`
    - `backend_app/jobs.py`, `backend_app/job_limits.py`, `backend_app/worker.py`, `backend_app/main.py`
    - `src/services/supabase_api_mode.py`, `src/services/ai_service.py`
