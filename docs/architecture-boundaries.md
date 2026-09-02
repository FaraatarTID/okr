# Canonical Backend Package and Facade Boundary

Documentation HQ: [README](../README.md)

Status: `VERIFIED` for P0-01.

This boundary record implements the decision required by [PRE_SAAS_ARCHITECTURE_BACKLOG.md](architecture/PRE_SAAS_ARCHITECTURE_BACKLOG.md), using the runtime evidence in [pre-saas-architecture-inventory.md](pre-saas-architecture-inventory.md). Repository-side import checks and facade call-path evidence are complete. Provider-backed deployment evidence remains governed by the separate BFF and release records.

## Proposed package roles

| Package or surface | Owns | Must not own |
|---|---|---|
| `backend_app` | FastAPI application assembly, HTTP routers, process configuration, health and observability wiring | Domain rules, direct browser presentation, migration policy |
| `src/domain` | Stable business concepts, invariants, and domain-level operations | FastAPI, Streamlit, Next.js, SQLAlchemy session details, deployment configuration |
| `src/services` | Application use cases and orchestration of domain operations | HTTP response shaping, browser session state, process startup |
| `src/crud.py` and `src/database.py` | Current persistence implementation and database connectivity | Transport concerns and UI behavior |
| `spa-bff` | Browser-facing mediation, session or route concerns assigned by its API contract | Python domain imports, direct database access, duplicated business rules |
| `spa-web` | Browser UI, client state, and presentation | Backend process startup and database access |
| `app.py` | Retired legacy facade; no supported callers remain | Any new runtime behavior |

## BFF deployment trade-off

`spa-bff` remains a separate service because it is the browser trust boundary:
it owns session mediation, route allowlisting, actor binding, request signing,
and the internal backend service token. The browser must not call
`backend_app` directly, and the BFF must not access the database or duplicate
domain rules. This separation is especially valuable when the backend is kept
private behind an internal network.

For a small single-tenant installation, the BFF and backend may be co-located
on the same host or provider project to reduce operational overhead. Co-location
does not permit bypassing the BFF, merging the code ownership boundaries, or
exposing the backend directly. Any future combined process or gateway mode
requires an explicit deployment design, health-check contract, and security
test before it becomes a supported profile; the current supported topology
continues to deploy `spa-bff` and `backend_app` as separate services.

## Repository packaging and ownership

The repository is a deliberate multi-service workspace, not a request to
introduce another package manager:

- `src/` is the shared Python application layer. `src/domain/` contains
  framework-independent business rules; `src/services/` contains application
  use cases and integrations; `src/crud.py`, `src/database.py`, and
  `src/models.py` contain the current persistence implementation.
- `backend_app/` is the deployable Python backend package. It owns FastAPI
  assembly, HTTP routers, process configuration, and the asynchronous worker.
  Its README is the service-level onboarding reference.
- The former root `app.py` compatibility facade has been retired. It was not a
  package root or a second runtime composition root.
- `spa-bff/` is the Node.js browser-facing mediation service. It owns the
  browser API allowlist, session mediation, and backend proxy contract.
- `spa-web/` is the Next.js browser application. It owns presentation, client
  state, and browser-facing routes; it must not access Python modules or the
  database directly.

Python uses the root `pyproject.toml` and `uv.lock` as the authoritative
dependency and development-tool configuration. The project intentionally sets
`tool.uv.package = false`: this is an application workspace, not a
distributable Python package. `backend_app/requirements.txt` remains only as a
deployment compatibility input while consumers migrate to the root uv
configuration.

JavaScript uses the existing root `package.json` npm workspaces for
`spa-bff/` and `spa-web/`. Their service manifests remain service-local, but
root-level `npm install`, `npm test`, and workspace scripts are the canonical
monorepo operations. No additional workspace manager is required.

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

## Facade migration record

The root `app.py` surface was classified as compatibility-only until caller
tracing proved otherwise. The inventory found no production, CLI, or deployment
callers; the remaining test callers were migrated to canonical service
contracts, and the file was removed. Any future compatibility surface must
document:

- the caller and supported user journey;
- the facade function or symbol used;
- the canonical replacement;
- a removal condition and owner.

New code should import from the canonical package or an explicitly documented interface, not from `app.py`.

Removal evidence: no supported imports or execution paths remain for the root
facade after the test migration. New code must use the canonical service
boundary or `backend_app`, never recreate a root compatibility facade.

The tested symbol-level migration map is recorded in [facade-migration-map.md](facade-migration-map.md).

## Enforcement evidence

- The repository import-boundary check passed: `python scripts/check_import_boundaries.py`.
- The module design/efficiency gate passed: `python scripts/verify_module_design_efficiency.py`.
- The two legacy facade test modules passed: `python -m pytest tests/test_app_cycle_cache_snapshot.py tests/test_app_rerun_cache_performance.py -q` completed 8 tests successfully.
- The canonical adapter contract passed 4 focused tests covering snapshot serialization and Monday-stable weekly cache buckets.
- The consolidated repository gate passed through the installed `just` runner using PowerShell as its shell: Ruff, typecheck, builds, Python tests, workspace tests, OpenAPI drift, and import boundaries completed successfully.
- Identify any `backend_app` imports that bypass the intended service or domain direction.
- Add or update a focused architectural test if an existing check does not cover the facade rule.
- The repository-side P0-01 boundary is `VERIFIED`; provider deployment and rollback evidence are not prerequisites for this package and remain tracked by the operational records.

## Decision handoff

P0-02 should consume this proposal when defining startup profiles. P0-03 should use the API contract boundary here when deciding whether `spa-bff` remains a separate deployable or becomes a thinner edge layer.

