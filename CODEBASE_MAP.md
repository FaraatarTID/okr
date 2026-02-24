Documentation HQ: [README](README.md)

# Codebase Map

Maintainer-focused map for the primary files and helper boundaries.

## How To Use This

- Start here before changing any high-traffic file (`app.py`, `components.py`, `crud.py`).
- Use this map to decide _where_ code should live and _which tests_ should be updated.
- Keep this file updated whenever a major module responsibility changes.

## Runtime Flow (At a Glance)

1. `streamlit_app/app.py` orchestrates app startup/auth/shell flow.
2. `streamlit_app/src/services/backend_launcher.py` handles background API startup in embedded mode.
3. `streamlit_app/src/ui/components.py` exposes a stable UI facade and delegates to `src/ui/*_helpers.py`.
4. `streamlit_app/src/crud.py` exposes a stable domain/data facade and delegates to `src/crud_*_helpers.py`.
5. `streamlit_app/src/database.py` and `streamlit_app/src/models.py` own persistence contracts.
6. Primary backend path: `backend_app/main.py` (API) -> `backend_app/jobs.py` -> `backend_app/worker.py`.

## Primary File Ownership Map

| File                                             | Responsibility                                       | Keep Here                                               | Move To                         | Key Dependencies                                             | Key Tests                                                                                                                                                                               |
| ------------------------------------------------ | ---------------------------------------------------- | ------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `streamlit_app/app.py`                           | Thin Streamlit coordinator and adapter wiring        | Entrypoint wiring, cache boundaries, helper delegation  | UI rendering/business logic     | `src.ui.app_*_helpers`, `src.crud`, `src.runtime_preflight`  | `tests/test_app_thin_coordinator_guardrails.py`, `tests/test_app_entry_helpers.py`, `tests/test_app_shell_helpers.py`, `tests/test_app_auth_helpers.py`, `tests/test_e2e_playwright_login_to_atlas.py` |
| `streamlit_app/src/ui/components.py`             | Stable UI compatibility facade                       | Cache wrappers, compatibility exports, bridge wiring    | Feature-specific UI logic       | `src/ui/*_helpers.py`, `components_bridge_helpers.py`        | `tests/test_dynamic_helper_contract_exports.py`, `tests/test_latency_audit_fixes.py`, `tests/test_backend_read_proxy_policy.py`, atlas UI test suite                                    |
| `streamlit_app/src/ui/dialogs.py`                | Dialog compatibility facade                          | Dialog routing/backward-compatible symbols              | Dialog implementation details   | `src/ui/dialogs_*_helpers.py`                                | `tests/test_remaining_helper_module_imports.py`, dialog-focused tests                                                                                                                   |
| `streamlit_app/src/crud.py`                      | Stable CRUD/domain facade API                        | Public contracts, policy constants, helper delegation   | Detailed business logic/queries | `src/crud_*_helpers.py`, `src/domain/*`, `src/database.py`   | `tests/test_crud_authorization.py`, `tests/test_crud_backend_mutation_proxy.py`, `tests/test_auth_rate_limit.py`, `tests/test_progress_rollup.py`, `tests/test_performance_hotpaths.py` |
| `streamlit_app/src/database.py`                  | Engine/session lifecycle and DB bootstrap/guardrails | Engine config, session context, migration/backup guards | Business rules                  | SQLModel/SQLAlchemy, runtime config                          | `tests/test_database_integrity.py`, runtime/preflight guardrail tests                                                                                                                   |
| `streamlit_app/src/models.py`                    | Schema and enum contracts                            | SQLModel entities, constraints, indexes, relationships  | Service/UI logic                | SQLModel metadata                                            | lifecycle/integrity tests (`tests/test_lifecycle_crud.py`, `tests/test_database_integrity.py`)                                                                                          |
| `streamlit_app/src/services/ai_service.py`       | AI orchestration service                             | Prompt/build context, provider/backend job dispatch     | UI/domain mutation rules        | `src/services/ai_provider.py`, `src/services/job_service.py` | AI/service tests and backend job tests                                                                                                                                                  |
| `streamlit_app/src/services/pdf_service.py`      | PDF/HTML export generation                           | PDFShift integration, HTML rendering templates          | UI orchestration                | `src/services/http_client.py`                                | PDF/export tests and runtime preflight tests                                                                                                                                            |
| `streamlit_app/src/services/backend_launcher.py` | Embedded backend lifecycle manager                   | Subprocess start, health polling, error log tailing     | Cluster process management      | `backend_app.run_api`, `os.environ`                          | cloud startup tests                                                                                                                                                                     |
| `backend_app/main.py`                            | Internal backend API for secure mutations/jobs       | Request validation, auth gate, endpoint orchestration   | Core CRUD rules                 | `backend_app.security.py`, `backend_app/jobs.py`, `src.crud` | backend API tests, security/rate-limit tests                                                                                                                                            |
| `backend_app/worker.py`                          | Async job worker loop                                | Claim/run/mark job lifecycle                            | Job business semantics          | `backend_app/job_runner.py`, `backend_app/jobs.py`           | worker/job lifecycle tests                                                                                                                                                              |

## Atlas UI Helper Spine

- Orchestration root: `streamlit_app/src/ui/atlas_workspace_orchestrator_helpers.py`
- Workspace facade wrappers: `streamlit_app/src/ui/atlas_workspace_helpers.py`
- Bootstrap/scope/focus split:
  - `streamlit_app/src/ui/atlas_workspace_bootstrap_helpers.py`
  - `streamlit_app/src/ui/atlas_workspace_scope_helpers.py`
  - `streamlit_app/src/ui/atlas_workspace_focus_helpers.py`
- Tabs/Map/Inspector split:
  - `streamlit_app/src/ui/atlas_workspace_tabs_helpers.py`
  - `streamlit_app/src/ui/atlas_map_tab_helpers.py`
  - `streamlit_app/src/ui/atlas_inspector_helpers.py`
- Session keys contract: `streamlit_app/src/ui/session_keys.py`

## End-to-End Test Spine

- Happy-path browser e2e: `tests/test_e2e_playwright_login_to_atlas.py`
- Coverage path: `Login -> Focus Map -> Start Timer`
- CI wiring: `.github/workflows/ci.yml` (Chromium install + gated e2e run)

Rule:

- Add new Atlas session keys in `streamlit_app/src/ui/session_keys.py` first, then consume constants in helpers.

## CRUD Helper Spine

- `streamlit_app/src/crud.py` is compatibility facade only.
- Primary slices:
  - `crud_auth_helpers.py`
  - `crud_create_helpers.py`
  - `crud_update_helpers.py`
  - `crud_delete_helpers.py`
  - `crud_query_helpers.py`
  - `crud_progress_helpers.py`
  - `crud_timer_helpers.py`
  - `crud_cycle_helpers.py`
  - `crud_checkin_helpers.py`
  - `crud_experiment_helpers.py`
  - `crud_team_helpers.py`
  - `crud_alignment_helpers.py`
  - `crud_reflection_helpers.py`

Rule:

- New logic goes into the relevant `crud_*_helpers.py`; keep `crud.py` wrapper signatures stable.

## Change Playbooks

### Add/Change UI behavior

1. Prefer `src/ui/*_helpers.py`.
2. Keep `components.py` as compatibility/wiring layer.
3. If state keys are added/changed, update `session_keys.py`.
4. Add/adjust helper unit tests first, then facade tests.

### Add/Change CRUD mutation

1. Implement in `crud_*_helpers.py`.
2. Wire through `crud.py` with backward-compatible signature.
3. Validate authorization path and backend-proxy behavior.
4. Update authorization + regression tests.

### Add backend API endpoint

1. Add schema in `backend_app/schemas.py`.
2. Add endpoint in `backend_app/main.py`.
3. Reuse `src.crud` public API (do not bypass policy in ad-hoc SQL).
4. Add API test plus failure-path coverage.

## Maintainer Guardrails

- Do not turn `app.py` into a feature module.
- Do not place new business logic directly in `components.py` or `crud.py`.
- Do not introduce new session key string literals when `session_keys.py` constant exists.
- Preserve compatibility exports used by monkeypatch-based tests.

## Suggested Ownership Convention

- Coordinator/facade files (`app.py`, `components.py`, `crud.py`, `dialogs.py`) should primarily change for:
  - wiring updates
  - compatibility surface updates
  - cache boundary changes
- Feature helper files should change for behavior.
