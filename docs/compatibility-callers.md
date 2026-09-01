# Compatibility Caller Inventory

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-04.

This inventory records the first repository-wide reference sweep for the root facade and launcher surfaces. It distinguishes production startup references from test and documentation references. A reference here is not, by itself, evidence that a surface can be removed.

## Root `app.py`

| Caller group | References found | Interpretation | Migration action |
|---|---|---|---|
| Cache snapshot tests | [tests/test_app_cycle_cache_snapshot.py](../tests/test_app_cycle_cache_snapshot.py) | Direct test dependency through `import app as app_module` | Preserve behavior while moving the tested facade contract to a canonical service interface |
| Cache performance tests | [tests/test_app_rerun_cache_performance.py](../tests/test_app_rerun_cache_performance.py) | Direct test dependency through `import app as app_module` | Keep performance assertions, then retarget them after the replacement interface exists |
| Runtime startup | [backend_app/run_api.py](../backend_app/run_api.py), [deploy/docker/docker-compose.yml](../deploy/docker/docker-compose.yml) | No observed API process reference to root `app.py` | Treat `app.py` as outside the canonical server startup chain |
| Documentation and archive references | [README.md](../README.md), [docs/archive/architecture-2026-08-31/ARCHITECTURE_BACKLOG_2026-08-31.md](archive/architecture-2026-08-31/ARCHITECTURE_BACKLOG_2026-08-31.md) | User guidance or historical evidence | Update current guidance only when the replacement is documented; preserve archive references |

The current evidence supports the classification `compatibility-only, still test-referenced`. Cycle and weekly-plan read-query callers now use canonical serializers directly. User read-query callers resolve the canonical serializer by default, while retaining one explicit `main._serialize_user` override for parity-sensitive backend tests and scope-specific deployments.

The facade boundary and app cache suites currently pass 29 combined tests. This confirms that the compatibility surface protects active cache, bootstrap, serialization, and shell-runtime behavior and must be migrated deliberately.

## Launcher surfaces

The supported journey mapping is recorded in [launcher-command-matrix.md](launcher-command-matrix.md). The preferred Docker command is `just start`; the Windows wrappers remain compatibility entrypoints for operator and local-development workflows. The launcher contract suite passed 2 tests, covering the wrapper command and process-shutdown contracts. `run_hybrid_app.bat --status` also completed successfully against the live Compose target, showing backend API and Postgres healthy with worker, BFF, and web running, without mutating services.

| Surface | References found | Current interpretation | Required follow-up |
|---|---|---|---|
| `run_hybrid_app.bat` | [tests/test_hybrid_app_launcher_script.py](../tests/test_hybrid_app_launcher_script.py), [README.md](../README.md) | Supported Docker operator path and test-covered contract | Keep as a thin wrapper over Compose and document its profile behavior |
| `run_hybrid_app_local.bat` | [tests/test_hybrid_app_launcher_script.py](../tests/test_hybrid_app_launcher_script.py), [README.md](../README.md), [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Supported local-development path | Keep while local workflows depend on it; remove duplicated policy incrementally |
| `run_okr_ui.bat` | [scripts/okr-launcher-ui.ps1](../scripts/okr-launcher-ui.ps1) | UI convenience entrypoint | Confirm every UI action delegates to a documented Docker or local path |
| `scripts/okr-launcher-ui.ps1` | [run_okr_ui.bat](../run_okr_ui.bat) | Operator orchestration | Keep orchestration separate from application construction |

## Result and limits

- No production startup reference to root `app.py` was found in the searched runtime paths.
- The import-boundary guard scans root production modules plus `src`, `backend_app`, and `scripts`; it passed with no production import of root `app.py`.
- `app.py` remains active through test imports, so cleanup must begin with an interface migration rather than deletion.
- Launcher surfaces are user-facing and test-referenced; they are not safe to remove as part of P0-04 without replacement-path evidence. The Docker wrapper now has a read-only status path for low-risk operational checks.
- This is a text-reference sweep. It does not prove dynamic imports, subprocess construction, or external operator usage.

## Next actions

1. Identify the specific facade symbols exercised by the two test modules.
2. Define their canonical replacement in `src/services` or an explicit compatibility adapter.
3. Add a deprecation and migration note before changing the root facade.
4. Reconcile launcher profile handling with [runtime-entrypoint-contract.md](runtime-entrypoint-contract.md) and [launcher-command-matrix.md](launcher-command-matrix.md).
5. Attach targeted check output before moving P0-04 to `VERIFIED`.
