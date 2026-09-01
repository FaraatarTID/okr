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

