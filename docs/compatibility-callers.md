# Compatibility Caller Inventory

Documentation HQ: [README](../README.md)

Status: `VERIFIED` for the root facade retirement; launcher cleanup remains operationally tracked.

This inventory records the first repository-wide reference sweep for the root facade and launcher surfaces. It distinguishes production startup references from test and documentation references. A reference here is not, by itself, evidence that a surface can be removed.

## Retired root `app.py`

| Caller group | References found | Interpretation | Migration action |
|---|---|---|---|
| Cache snapshot tests | [tests/test_app_cycle_cache_snapshot.py](../tests/test_app_cycle_cache_snapshot.py) | Migrated to `src.services.app_shell_runtime` | Preserve the canonical snapshot-cache contract |
| Cache performance tests | [tests/test_app_rerun_cache_performance.py](../tests/test_app_rerun_cache_performance.py) | Migrated to `src.services.app_shell_runtime` | Preserve zero-query cache-hit assertions |
| Runtime startup | [backend_app/run_api.py](../backend_app/run_api.py), [deploy/docker/docker-compose.yml](../deploy/docker/docker-compose.yml) | No observed API process reference to root `app.py` | Treat `app.py` as outside the canonical server startup chain |
| Documentation and archive references | [README.md](../README.md), [docs/archive/architecture-2026-08-31/ARCHITECTURE_BACKLOG_2026-08-31.md](archive/architecture-2026-08-31/ARCHITECTURE_BACKLOG_2026-08-31.md) | User guidance or historical evidence | Update current guidance only when the replacement is documented; preserve archive references |

The current evidence supports retiring the root facade. Cycle, weekly-plan,
serializer, selector, bootstrap, and cache tests now use canonical service
contracts directly. No production, CLI, or deployment caller was found.

The facade boundary and app cache suites currently pass 29 combined tests. This confirms that the compatibility surface protects active cache, bootstrap, serialization, and shell-runtime behavior and must be migrated deliberately.

## `backend_app.main` facade (P4.5, in progress)

`backend_app/main.py` re-exports names that routers, handlers and tests reach through `main.<name>`. The
retirement is one module per commit: move the caller to the real owner, then drop the matching re-export or
`noqa: F401` once no caller remains. The lists below are from a text search of `backend_app/` on 2026-09-29; like
the sweep above, they do not prove dynamic imports.

| Module | Reaches `backend_app.main` | Status |
|---|---|---|
| [security.py](../backend_app/security.py) | Two function-local `from backend_app import main` lookups of the scope resolver | **Done.** Calls [scope_resolution.py](../backend_app/scope_resolution.py) directly. `resolve_actor_username` moved to the leaf [actor_identity.py](../backend_app/actor_identity.py) to avoid a `security` to `scope_resolution` cycle |
| [authentication.py](../backend_app/authentication.py) | `sys.modules.get("backend_app.main")` lookup of `_require_admin_actor_scope` | **Done.** Calls the helper directly |
| [main_runtime_helpers.py](../backend_app/main_runtime_helpers.py) | Three function-local imports (lines 62, 89, 185) that honour patches made on the facade | Not started |
| [main_mutation_handlers.py](../backend_app/main_mutation_handlers.py) | One function-level and eight nested imports | Not started |
| [main_workflow_handlers.py](../backend_app/main_workflow_handlers.py) | One function-level import | Not started |
| `backend_app/routers/*` | `Depends(main.…)` and `main._require_admin_actor_scope(...)` | Not started |

Two seams were deliberately kept because callers still depend on them, so their `noqa: F401` markers stay:

- `require_control_plane_operator` is still read from the facade by the control-plane router through `getattr(main, …)`.
- `require_service_access` is still bound by every router as `Depends(main.require_service_access)`, and tests
  override it on the facade with `dependency_overrides`.

Tests that patched `backend_main._resolve_scope_for_actor` to influence the service dependency were moved to patch
`backend_app.scope_resolution`, which is the seam the dependency now uses. Handlers and routers still resolve the
scope through the facade, so patches on the facade keep working there until those modules move.
### Measured cost of the remaining modules (2026-09-30)

From a text search of `backend_app/` and `tests/` (dynamic access is not counted). "Patch sites" are
`monkeypatch.setattr(backend_main, "<name>", ...)` calls in tests on a name the module reaches through the facade.

| Module | Names reached through the facade | Of those, patched by tests | Patch sites | Patched names |
|---|---|---|---|---|
| `main_runtime_helpers.py` | 2 | 1 | 15 | `get_session_context`; also holds the patched-resolver seam (`_resolve_scope_for_actor` versus `_runtime`) |
| `main_workflow_handlers.py` | 16 | 5 | 17 | `_resolve_scope_for_actor`, `create_check_in`, `delete_alignment`, `is_supabase_api_mode_enabled`, `update_experiment` |
| `main_mutation_handlers.py` | 13 | 7 | 20 | `create_goal`, `create_key_result`, `create_objective`, `create_task`, `create_user`, `is_supabase_api_mode_enabled`, `update_task` |
| `read_query_helpers.py` (not in the table above) | 55 | 8 | 24 | `_resolve_scope_for_actor`, `_serialize_task`, `get_active_cycles`, `get_all_cycles`, `get_all_users`, `get_session_context`, `get_user_by_username`, `summarize_audit_events` |

Why this is not a per-module job like `security.py`:

- `is_supabase_api_mode_enabled` (8 patch sites) and `get_session_context` (15 patch sites) are read through the facade by several of these modules at once. Moving one module makes a test that patches the facade stop affecting it: it fails, or passes against the real function. Both seams have to move together, with their tests, in one change.
- The routers still bind `Depends(main.require_service_access)`, and three test files override it on the facade.
- `read_query_helpers.py` reaches the facade 55 ways and was not counted in the first inventory.

Not done, on purpose: no module was moved in this pass. The counts are a text search of one commit, not a proof of what
a move would break.

## Launcher surfaces

The supported journey mapping is recorded in [launcher-command-matrix.md](launcher-command-matrix.md). The preferred Docker command is `just start`; the Windows wrappers under `scripts/windows/` remain compatibility entrypoints for operator and local-development workflows. The launcher contract suite passed 2 tests, covering the wrapper command and process-shutdown contracts. `scripts/windows/run_hybrid_app.bat --status` also completed successfully against the live Compose target, showing backend API and Postgres healthy with worker, BFF, and web running, without mutating services.

| Surface | References found | Current interpretation | Required follow-up |
|---|---|---|---|
| `scripts/windows/run_hybrid_app.bat` | [tests/test_hybrid_app_launcher_script.py](../tests/test_hybrid_app_launcher_script.py), [README.md](../README.md) | Supported Docker operator path and test-covered contract | Keep as a thin wrapper over Compose and document its profile behavior |
| `scripts/windows/run_hybrid_app_local.bat` | [tests/test_hybrid_app_launcher_script.py](../tests/test_hybrid_app_launcher_script.py), [README.md](../README.md), [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Supported local-development path | Keep while local workflows depend on it; remove duplicated policy incrementally |
| `scripts/windows/run_okr_ui.bat` | [scripts/okr-launcher-ui.ps1](../scripts/okr-launcher-ui.ps1) | UI convenience entrypoint | Confirm every UI action delegates to a documented Docker or local path |
| `scripts/okr-launcher-ui.ps1` | [run_okr_ui.bat](../scripts/windows/run_okr_ui.bat) | Operator orchestration | Keep orchestration separate from application construction |

## Result and limits

- No production startup reference to root `app.py` was found in the searched runtime paths.
- The import-boundary guard scans root production modules plus `src`, `backend_app`, and `scripts`; it passed with no production import of root `app.py`.
- `app.py` was deleted after all test imports were migrated to canonical service contracts.
- Launcher surfaces are user-facing and test-referenced; their canonical copies live under `scripts/windows/`. The former root duplicates were removed after the replacement-path evidence was established. The Docker wrapper has a read-only status path for low-risk operational checks.
- This is a text-reference sweep. It does not prove dynamic imports, subprocess construction, or external operator usage.

## Next actions

1. Keep the canonical service boundary covered as runtime behavior evolves.
2. Reject any new root-level compatibility facade without an explicit ADR.
3. Reconcile launcher profile handling with [runtime-entrypoint-contract.md](runtime-entrypoint-contract.md) and [launcher-command-matrix.md](launcher-command-matrix.md).

