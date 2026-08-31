# Pre-SaaS Architecture Inventory

Back to [Documentation HQ](README.md).

Status: `IN-PROGRESS` for P0-00.

This is an evidence-based first-pass inventory for [PRE_SAAS_ARCHITECTURE_BACKLOG.md](../PRE_SAAS_ARCHITECTURE_BACKLOG.md), based on [ARCHITECTURE_DELIVERY_SYSTEM.md](ARCHITECTURE_DELIVERY_SYSTEM.md). It records observed runtime surfaces and proposed classifications; it does not yet establish the final package or deployment boundaries.

## Observed runtime surfaces

| Surface | Evidence | Current classification | Primary follow-up |
|---|---|---|---|
| Backend API application | [backend_app/main.py](../backend_app/main.py), [backend_app/main_app_bootstrap.py](../backend_app/main_app_bootstrap.py) | Canonical backend candidate | P0-01: formalize package ownership and imports |
| Backend API process | [backend_app/run_api.py](../backend_app/run_api.py) | Canonical API entrypoint candidate | P0-02: define supported startup contract |
| Background worker | [backend_app/worker.py](../backend_app/worker.py) | Canonical worker entrypoint candidate | P0-02: define process and health contract |
| Shared domain and persistence | [src/](../src/), including `src/domain`, `src/services`, `src/crud.py`, `src/models.py`, and `src/database.py` | Shared implementation surface | P0-01: separate domain, adapter, and interface ownership |
| SPA backend-for-frontend | [spa-bff/src/server.ts](../spa-bff/src/server.ts), [spa-bff/package.json](../spa-bff/package.json) | Separate deployable candidate | P0-03: record BFF boundary ADR |
| SPA web client | [spa-web/package.json](../spa-web/package.json), [spa-web/README.md](../spa-web/README.md) | Separate Next.js deployable | P0-03: confirm browser/API contract |
| Container deployment | [deploy/docker/docker-compose.yml](../deploy/docker/docker-compose.yml), [deploy/docker/Dockerfile](../deploy/docker/Dockerfile) | Active self-hosted runtime | P0-02 and P0-06: profile and rollback evidence |
| Kubernetes deployment | [deploy/k8s/](../deploy/k8s/) | Secondary deployment surface | P0-02: reconcile supported runtime matrix |
| Database migrations | [alembic/](../alembic/) | Deployment dependency | P0-04: migration policy and compatibility evidence |
| Root compatibility facade | [app.py](../app.py) | Legacy or compatibility candidate | P0-00: trace remaining callers before retirement decision |
| Environment launchers | [run_hybrid_app.bat](../run_hybrid_app.bat), [run_hybrid_app_local.bat](../run_hybrid_app_local.bat), [run_okr_ui.bat](../run_okr_ui.bat), [scripts/okr-launcher-ui.ps1](../scripts/okr-launcher-ui.ps1) | Compatibility and operator wrappers | P0-00/P0-02: map supported user journeys to one contract |
| Delivery and quality gates | [.github/workflows/](../.github/workflows/), [scripts/](../scripts/) | Architectural control plane | P0-05: preserve gates while boundaries change |

## Observed startup topology

```text
Supported operator commands
  just start / run_hybrid_app.bat / local launcher UI
    |
    +--> deploy/docker/docker-compose.yml
           |
           +--> backend-api
           |      python -m backend_app.run_api
           |        -> backend_app.main:app
           |           -> create_app()
           |              -> build_main_app()
           |
           +--> backend-worker
           |      python -m backend_app.worker
           |
           +--> spa-bff
           |      node dist/src/server.js (container)
           |      npm run dev (local)
           |
           +--> spa-web
                  next start (container/local production)
                  next dev (local development)

Root app.py is not part of the observed API container startup chain.
```

The local launcher also starts the API and worker through the same Python module entrypoints while starting the BFF and web client with their package scripts. The Docker Compose path is the clearest current system boundary: API, worker, BFF, and web are distinct processes.

## Initial ownership matrix

| Responsibility | Current owner candidate | Boundary rule to preserve |
|---|---|---|
| HTTP API composition and observability | `backend_app` | API assembly stays out of `src/domain` |
| Domain rules and use cases | `src/domain` and `src/services` | Domain code must not depend on web or deployment adapters |
| Persistence and external integrations | `src/crud.py`, `src/database.py`, related adapters | Access goes through explicit adapter interfaces after P0-01 |
| Browser-facing session and route mediation | `spa-bff` | BFF remains distinct until the P0-03 ADR resolves its fate |
| Browser UI | `spa-web` | UI owns presentation and client interaction, not database access |
| Process orchestration | Compose, launchers, and deployment manifests | Operator paths should converge on documented entrypoints |
| Schema evolution | `alembic` | Migration ordering and rollback behavior are explicit before SaaS cutover |
| Architectural enforcement | CI workflows and `scripts/` checks | Every boundary change retains machine-checkable evidence |

## P0-00 remaining questions

- Which callers still import or execute `app.py`, and can it be safely labeled compatibility-only?
- Which launcher paths are supported for development, self-hosted deployment, and release operations?
- Is Kubernetes a supported production target or a maintained secondary surface?
- Which runtime topology is the baseline for the P0-03 BFF decision and P0-06 rollback rehearsal?

## Handoff to the next backlog items

P0-00 now has a first-pass inventory and a proposed topology. P0-01 should turn the ownership candidates into explicit package boundaries and import rules. P0-02 should then make the API, worker, BFF, and SPA process contract reproducible across the supported environments.
