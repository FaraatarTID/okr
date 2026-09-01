# Canonical Backend Package and Facade Boundary

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-01.

This working proposal implements the boundary decision required by [PRE_SAAS_ARCHITECTURE_BACKLOG.md](architecture/PRE_SAAS_ARCHITECTURE_BACKLOG.md), using the runtime evidence in [pre-saas-architecture-inventory.md](pre-saas-architecture-inventory.md). It is intentionally a proposal until import checks and facade call-path evidence are captured.

## Proposed package roles

| Package or surface | Owns | Must not own |
|---|---|---|
| `backend_app` | FastAPI application assembly, HTTP routers, process configuration, health and observability wiring | Domain rules, direct browser presentation, migration policy |
| `src/domain` | Stable business concepts, invariants, and domain-level operations | FastAPI, Streamlit, Next.js, SQLAlchemy session details, deployment configuration |
| `src/services` | Application use cases and orchestration of domain operations | HTTP response shaping, browser session state, process startup |
| `src/crud.py` and `src/database.py` | Current persistence implementation and database connectivity | Transport concerns and UI behavior |
| `spa-bff` | Browser-facing mediation, session or route concerns assigned by its API contract | Python domain imports, direct database access, duplicated business rules |
| `spa-web` | Browser UI, client state, and presentation | Backend process startup and database access |
| `app.py` | Temporary compatibility facade only, if still required by callers | New canonical runtime behavior |

## Dependency direction

```text
backend_app transport and process composition
                 |
                 v
       application services and use cases
                 |
                 v
          domain rules and models
                 ^
                 |
       persistence and external adapters

spa-web --> spa-bff --> documented backend API contract
```

The arrows describe permitted request flow. Persistence adapters may implement interfaces needed by application services, but domain rules must remain independent of the concrete database and web frameworks. The BFF communicates with the backend through an API contract rather than importing Python modules.

## Canonical API assembly path

The supported API process should continue to assemble the application through the following path:

```text
backend_app.run_api
  -> backend_app.main:app
     -> create_app()
        -> build_main_app()
```

This keeps process startup separate from application construction and makes `backend_app.main` the canonical backend surface for deployment configuration. The worker remains a separate process through `backend_app.worker`.

## Facade migration rule

The root `app.py` surface is classified as compatibility-only until caller tracing proves otherwise. It may delegate to canonical services during migration, but it must not become a second application composition root. Any remaining caller should be documented with:

- the caller and supported user journey;
- the facade function or symbol used;
- the canonical replacement;
- a removal condition and owner.

New code should import from the canonical package or an explicitly documented interface, not from `app.py`.

The tested symbol-level migration map is recorded in [facade-migration-map.md](facade-migration-map.md).

## Enforcement work still required

- The repository import-boundary check passed: `python scripts/check_import_boundaries.py`.
- The module design/efficiency gate passed: `python scripts/verify_module_design_efficiency.py`.
- The two legacy facade test modules passed: `python -m pytest tests/test_app_cycle_cache_snapshot.py tests/test_app_rerun_cache_performance.py -q` completed 8 tests successfully.
- The canonical adapter contract passed 4 focused tests covering snapshot serialization and Monday-stable weekly cache buckets.
- The consolidated repository gate passed through the installed `just` runner using PowerShell as its shell: Ruff, typecheck, builds, Python tests, workspace tests, OpenAPI drift, and import boundaries completed successfully.
- Trace remaining imports and execution paths for `app.py`.
- Identify any `backend_app` imports that bypass the intended service or domain direction.
- Add or update a focused architectural test if an existing check does not cover the facade rule.
- Mark this proposal `VERIFIED` only after the evidence is attached to the status ledger.

## Decision handoff

P0-02 should consume this proposal when defining startup profiles. P0-03 should use the API contract boundary here when deciding whether `spa-bff` remains a separate deployable or becomes a thinner edge layer.

