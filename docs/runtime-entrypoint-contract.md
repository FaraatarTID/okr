# Runtime and Deployment Entrypoint Contract

Documentation HQ: [README](../README.md)

Status: `IN-PROGRESS` for P0-02.

This contract turns the observed startup paths in [pre-saas-architecture-inventory.md](pre-saas-architecture-inventory.md) into the working runtime baseline for the pre-SaaS architecture. It documents commands and responsibilities; it does not yet replace the existing launchers or prove every profile.

## Supported process contract

| Process | Container entrypoint | Local entrypoint | Responsibility | Readiness expectation |
|---|---|---|---|---|
| Backend API | `python -m backend_app.run_api` | `python -m backend_app.run_api` | Serve the canonical FastAPI application | API health endpoint reports ready dependencies |
| Backend worker | `python -m backend_app.worker` | `python -m backend_app.worker` | Execute background work independently of HTTP serving | Worker remains alive and reports operational status through its supported mechanism |
| SPA BFF | `node dist/src/server.js` | `npm run dev` in `spa-bff` | Mediate browser-facing requests and session or route concerns | BFF health endpoint accepts local and deployed probes |
| SPA web | `next start` after build | `next dev` for development | Serve the browser application | Web process is reachable and points to the configured BFF/API endpoint |

## Container baseline

The baseline self-hosted topology is the four application processes defined by [docker-compose.yml](../deploy/docker/docker-compose.yml):

```text
spa-web --> spa-bff --> backend-api --> database
                            |
                            +--> backend-worker --> database / external services
```

The API and worker are separate processes even when they share the same image and Python package. The BFF and web client remain separate deployables until the P0-03 boundary decision is complete.

## Operator paths

| Use case | Primary path | Contract status |
|---|---|---|
| Self-hosted application start | `just start` or `run_hybrid_app.bat` | Supported candidate; resolves the self-hosted `database` profile unless an explicit compatibility override is selected |
| Local development | `run_hybrid_app_local.bat` or the launcher UI local mode | Supported candidate; starts the same Python module entrypoints |
| API-only operation | `python -m backend_app.run_api` | Canonical process contract |
| Worker-only operation | `python -m backend_app.worker` | Canonical process contract |
| Release deployment | `.github/workflows/docker-deploy.yml` with Compose | Supported candidate; readiness evidence required |
| Kubernetes operation | `deploy/k8s/` manifests | Secondary surface pending runtime-matrix reconciliation |

Operator wrappers may remain for usability, but they should delegate to these process contracts rather than create alternate application startup behavior.

## Configuration rules

- Every supported deployment declares one explicit runtime profile and one explicit data backend.
- SaaS or release operation must fail closed when required database, secret, or external-service configuration is absent.
- Local development may provide a documented development backend, but fallback behavior must be visible in launcher output and must not be treated as production readiness.
- API, worker, BFF, and web processes receive configuration through their documented environment contract, not through implicit working-directory assumptions.
- Health and readiness probes must distinguish process liveness from dependency readiness.
- A profile change must be represented in deployment evidence and the rollback record.

## Canonicalization rules

1. New deployment definitions use the Python module entrypoints for the API and worker.
2. New operator scripts call the documented Compose or local process contract instead of importing `app.py`.
3. The root `app.py` facade remains outside the canonical server startup chain.
4. Any alternate entrypoint requires an explicit status, owner, supported environment, and retirement or reconciliation plan.

## Evidence still required

- Runtime matrix check passed: `python scripts/check_deploy_runtime_matrix.py` exited 0.
- Bounded readiness gate passed against Compose: all five services were running; backend and BFF health returned `ok`; SPA root returned healthy HTML.
- Live backend health payload confirmed `configured_mode=supabase_api`, `data_access_mode=supabase_api`, and `dead_jobs=0` for the captured compatibility Compose baseline.
- SaaS target is explicitly `OKR_DEPLOYMENT_PROFILE=single_tenant_saas` with `OKR_DATA_ACCESS_MODE=database`; `supabase_api` is an alpha/on-premise compatibility mode and is not the SaaS target.
- Disposable SaaS review configuration passed `python scripts/check_deploy_config.py --mode runtime` with `OKR_DEPLOYMENT_PROFILE=single_tenant_saas` and `OKR_DATA_ACCESS_MODE=database`; the local Compose URL produced only the expected non-pooler warning.
- An isolated disposable Postgres database ran the SaaS `database` profile migrations through `drop_global_cycle_index`; the temporary API returned HTTP 200 with `data_access_mode=database`, `configured_mode=database`, and `dead_jobs=0`. The temporary database was removed after the probe.
- Record the effective Compose profile and data backend for each remaining supported environment.
- Capture a readiness check for API, worker, BFF, and web processes.
- Document rollback commands and the last-known-good image or release in P0-06.
- Mark P0-02 `VERIFIED` only after the runtime matrix, profile enforcement, and readiness checks pass against the explicit SaaS `database` target, not only the compatibility `supabase_api` baseline.

## Handoff

P0-03 can now evaluate the BFF as a boundary against a defined process topology. P0-06 can use this contract as the baseline for rollback rehearsal and evidence capture.

