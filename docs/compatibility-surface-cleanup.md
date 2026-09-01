# Root Script and Compatibility Surface Cleanup

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-04.

This workstream identifies root-level facades and operator wrappers that could preserve historical behavior while the canonical API, worker, BFF, and SPA topology is established. No surface is removed by this document alone.

## Surface classification

| Surface | Current role | Cleanup disposition | Evidence still required |
|---|---|---|---|
| Retired `app.py` | Former root Python compatibility facade | Removed after callers migrated to canonical services | [compatibility-callers.md](compatibility-callers.md) |
| [run_hybrid_app.bat](../scripts/windows/run_hybrid_app.bat) | Docker-oriented operator wrapper | Retain as a thin supported wrapper | Confirm it delegates to the documented Compose contract |
| [run_hybrid_app_local.bat](../scripts/windows/run_hybrid_app_local.bat) | Local multi-process launcher | Retain for local development during transition | Map supported local journeys and remove duplicated policy |
| [run_okr_ui.bat](../scripts/windows/run_okr_ui.bat) | Launcher UI entrypoint | Retain as an operator convenience wrapper | Confirm UI actions map one-to-one to supported commands |
| [scripts/okr-launcher-ui.ps1](../scripts/okr-launcher-ui.ps1) | Launcher UI orchestration | Retain only as orchestration, not application composition | Trace Docker/local branches and configuration handling |
| [justfile](../justfile) | Task and developer command surface | Canonical task documentation candidate | Reconcile `start`, checks, and runtime profiles |
| Root ad hoc startup commands | Historical or undocumented process paths | Deprecate when discovered | Search results plus owner confirmation |

## Cleanup rules

- A compatibility surface must have one named owner and one supported purpose.
- Wrappers may select an environment or invoke a process, but must not duplicate backend application assembly.
- New code must not recreate or import a root-level compatibility facade when a canonical service or API interface exists.
- A wrapper cannot be deleted until its callers, user journeys, and replacement command are recorded.
- Deprecation must include a visible warning or release note where users can encounter the old path.
- Removal requires a rollback or restoration path for the supported environment it served.
- The cleanup must preserve the canonical entrypoints documented in [runtime-entrypoint-contract.md](runtime-entrypoint-contract.md).
- The tested facade symbol migration is tracked in [facade-migration-map.md](facade-migration-map.md).
- `python scripts/check_import_boundaries.py` is the focused guard against new production imports of the retired root facade name.

## Target end state

```text
Operator or developer command
          |
          v
Documented environment wrapper
          |
          v
Canonical process contract
  backend_app.run_api
  backend_app.worker
  spa-bff package scripts
  spa-web package scripts
```

The retired root facade was outside this startup path. The canonical service and backend entrypoints are now the only supported runtime surfaces.

## Safe cleanup sequence

1. Inventory imports, subprocess calls, documentation links, and user-facing references for each surface.
2. Assign an owner and replacement path.
3. Add a deprecation marker where the surface is still externally used.
4. Migrate callers and update operator documentation.
5. Remove only after the replacement path has evidence in CI or deployment checks.
6. Record the removal and rollback boundary in the worklog.

## P0-04 acceptance evidence

- [compatibility-callers.md](compatibility-callers.md) covering the retired facade and each launcher.
- A table mapping every supported journey to its replacement command.
- Proof that wrappers invoke canonical module or package entrypoints.
- No undocumented duplicate application composition root.
- Updated documentation links and release/deprecation notes.
- A focused check preventing new imports of the compatibility facade.

P0-04 should move to `VERIFIED` only after these artifacts are attached to the status ledger and the cleanup is shown to preserve supported operator journeys.

