# Architecture

Documentation HQ: [README](README.md)

Maintainer file ownership and change map: [CODEBASE_MAP.md](CODEBASE_MAP.md)

## System Overview

This repository is an OKR platform with a SPA-first runtime (`spa-web` + `spa-bff` + backend services).

Runtime topology:

- `spa-web` (Next.js) provides primary UX.
- `spa-bff` provides browser-facing API boundary, auth/session mediation, and allowlisted proxying.
- `backend-api` (FastAPI control plane) and `backend-worker` (async execution plane) own mutations, reads, and heavy/background work.

- Primary UI entrypoint: `spa-web/`
- Browser/API boundary: `spa-bff/`
- Shared domain/data operations: shared runtime modules under `src/`
- Extracted domain modules:
  - `src/domain/authorization.py` (ownership/RBAC predicates + authorizers)
  - `src/domain/analytics.py` (hot-path analytics/reporting queries)
- Persistence: Alembic migrations in `alembic/`
- External integrations: `src/services/ai_service.py`, `src/services/pdf_service.py`
- Shared business helpers: `src/utils/deadline_utils.py`
- Backend services & launcher:
  - `backend_app/main.py`, `backend_app/worker.py`, `backend_app/jobs.py`

## Runtime Topology

Primary data/control flow:

1. UI and session:

- Browser -> `spa-web` -> `spa-bff`.
- `spa-web` handles rendering/state and role-aware UX.
- `spa-bff` enforces boundary policy before forwarding to backend services.

2. Synchronous domain mutations:

- `spa-bff` -> `backend-api` mutation endpoints -> CRUD (`src/crud.py`) -> Supabase PostgreSQL.
- Default behavior (all environments): fail closed with explicit user-facing error when backend transport fails.
- Scope (frontend write paths): Goal/Objective/KeyResult/Task CRUD, timer start/stop, user/cycle/team admin mutations, Learning Loop mutations (check-ins/experiments/retrospectives/weekly plans/outcomes), alignment mutations, and work-log deletes.

3. Synchronous read/query paths:

- `spa-bff` -> `backend-api` read endpoints -> CRUD (`src/crud.py`) -> Supabase PostgreSQL.
- Atlas snapshot/runtime reads and leadership read paths are backend-served.

4. Async heavy workflows:

- Frontend -> `backend-api` (`/v1/jobs`) with `OKR_BACKEND_SERVICE_TOKEN`.
- `backend-api` enqueues durable jobs in `async_job`.
- `backend-worker` claims and executes jobs (`ai.generate_json`, `pdf.weekly`).
- Frontend polls job status and renders result.

5. Timer routing:

- Timer service -> `backend-api` (`/v1/timer/start|stop`).
- Runtime behavior is fail-closed if backend is unavailable (no local fallback execution).

6. PDF rendering:

- Supported binary renderers:
  - `PDFShift` (`PDF_METHOD=pdfshift`, requires API key)
  - `Chromium` via Playwright (`PDF_METHOD=chromium`)
- If PDF binary rendering is unavailable, UI falls back to HTML export.

## Security and Isolation Boundaries

- DB boundary:
  - Single source of truth in Supabase PostgreSQL.
  - Connection policy expects transaction pooler endpoint (`:6543`).
  - Runtime DSN should use a least-privilege app user (not `postgres`) except explicit break-glass overrides.
  - Postgres engine defaults to `NullPool` in app runtimes to align with Supabase PgBouncer transaction pooling.
- Service boundary:
  - `backend-api` authenticates service calls using `OKR_BACKEND_SERVICE_TOKEN`.
  - Optional cryptographic request signing (`OKR_BACKEND_SIGNING_SECRET`) enforces signed/replay-protected internal calls.
  - Basic in-memory IP rate limiting protects API endpoints.
- Network boundary:
  - Public ingress should expose only reverse proxy/app paths.
  - `backend-api` should remain private (loopback/internal bind in compose by default).
- Data egress boundary:
  - AI calls are policy-gated by `ALLOW_EXTERNAL_AI`.
  - `AI_PROVIDER=openai_compatible` supports internal/self-hosted gateways.

## Module Boundaries

1. UI boundary

- Owns SPA rendering and session state orchestration.
- Calls CRUD/service functions; does not own database transactions.

2. Domain boundary (`crud.py` facade + `src/domain/*` + `deadline_utils.py`)

- Owns business rules for:
  - CRUD and hierarchy traversal
  - authorization checks (owner/manager/admin)
  - check-ins, reports, leadership metrics, timer semantics
  - deadline health/status logic
- Keeps rules testable without UI runtime.

3. Persistence boundary (`database.py`, `models.py`, migrations)

- Owns connection lifecycle, schema, constraints, and indexes.
- Guarantees FK integrity, check constraints, and migration-driven schema updates.
- Manages `LifecycleState` transitions and persistence.

4. Integration boundary (`services/*` + `backend_app/*`)

- Owns AI analysis and PDF/report output.
- Should not contain core authorization logic.
- Backend API/worker isolate heavy operations from frontend request cycles.

## Critical Request/Data Flows

1. Objective / KR / Task creation

- UI dialog submits to `create_goal` / `create_objective` / `create_key_result` / `create_task`.
- CRUD validates actor permissions using ancestor goal ownership.
- DB commit persists node on Supabase PostgreSQL.

1a. Lifecycle State Transitions

- UI Inspector submits state change.
- `src/domain/lifecycle.py` validates the transition (e.g., DRAFT -> ACTIVE).
- `crud.py` applies the change and triggers a cascade (Objective state -> child KRs).

1b. Hierarchy navigation flow (Atlas mode)

- SPA routes dispatch to Atlas workspace views.
- Top command bar handles quick jump and role-aware scope controls.
- Focus selection and timer commitment are consolidated inside `Focus Map` to avoid duplicated surfaces.
- Workspace uses two surfaces:
  - `Focus Map`: first-glance clickable treemap + urgency legend + ranked focus candidates
  - `Inspector`: deep edit/read context for selected node

## Atlas UX Architecture (v2)

Interaction model is intentionally split into control-plane and work-plane:

1. Control-plane: Focus Map Commit Loop

- Focus selection and sprint control happen in one place (`Focus Map`).
- Primary timer commitment happens in `Commit Spotlight`.
- Focused task state is sticky across tab changes.
- Human-first prompts and status chips provide instant context without metric overload.

2. Work-plane: Progressive disclosure

- `Focus Map` is the first-glance visual overview for focus choice.
- `Focus Map` encodes urgency with explicit visual semantics while presenting a simplified human label (`Needs care` / `On track` / `Complete`).
- Treemap urgency is intentionally grouped into a coherent `Needs care` tone to avoid visual overload.
- Map key semantics are split for clarity:
  - tile fill colors represent status (`Needs care` / `On track` / `Complete`)
  - outline/ring states represent navigation context (`Focused task` / `Selected node` / `Path context`)
- `Focus Map` defaults to full scope lens and supports branch lens for local drill-in.
- `Inspector` is optimized for depth (details and edits).

3. State contracts

- Selected node reference is the single source of truth for current node context.
- Focus task reference is the explicit focus target for timer operations.
- A map click must update the selected reference; navigation path and `Inspector` are derived from that shared selection.
- `Focus Map` and `Inspector` mutate only these shared selection keys.

4. Permission contract

- Timer mutations remain ownership-gated (`owner_id == actor_id`) at UI + CRUD boundaries.

5. Attention classification contract

- A node is `Needs attention` when incomplete and either:
  - marked overdue/risk by deadline/status evaluation, or
  - below progress threshold (40%).

2. Check-in flow

- UI weekly check-in submits `create_check_in`.
- CRUD creates `check_in`, updates KR value/progress, commits transaction.
- `get_krs_needing_checkin` identifies stale/missing KR updates for the selected cycle.

3. Progress and scoring flow

- Task/KR fields are stored in DB and consumed by dashboard/report aggregations.
- Deadline health is computed via `get_deadline_status` (supports both ORM objects and dict payloads).
- Leadership rollups aggregate task progress, deadline status, check-in freshness, confidence, and risk.

4. Permission / sharing flow

- Mutating actions call `_authorize_goal_mutation`.
- Owner, manager-of-owner, and admin paths are enforced before changes are committed.
- Read-sensitive node retrieval can be actor-scoped via `get_node(..., actor_username=...)`.
- AI node analysis (`analyze_node`) can use this actor-scoped read path before prompt context assembly.

5. Async job flow

- `run_job_and_wait` submits to `backend-api` when backend mode is enabled.
- Job lifecycle: `pending -> running -> succeeded|failed|cancelled`.
- Worker writes result/error payloads into `async_job`.
- Frontend reads job state and surfaces final output.
- Job submission is guarded by per-user/per-team quotas and idempotency keys in backend API.
- In PostgreSQL runtimes, worker claim path uses `FOR UPDATE SKIP LOCKED` semantics to reduce queue-head contention across concurrent workers.
- Worker resiliency guardrails include capped attempts, terminal handling for non-retryable payload failures, and bounded error-text persistence.

## Invariants and Guardrails

### OKR Methodology Rules
- Goals and Objectives are time-bounded by the OKR cycle, NOT by individual deadlines.
- Only Key Results have measurable progress (measured through check-in sessions).
- Only Tasks have deadlines.
- Progress on Goals/Objectives is a computed rollup from child KRs — it is not user-set.
- AI sync projects KR progress based on completed work; discrepancies between projection and actual go into retro sessions as experiments.

### Technical Guardrails

- Goal ownership is anchored on `goal.owner_id`.
- Mutations require `actor_username` for goal-scoped entities.
- DB constraints enforce progress ranges, non-negative durations, and single open work log per task.
- Hot-path query budgets are tested in `tests/test_performance_hotpaths.py` to prevent N+1 regressions.
- Runtime preflight defaults to strict (`OKR_STRICT_RUNTIME_PREFLIGHT=true`) for fail-fast misconfiguration detection.
- Runtime preflight validates backend production wiring (API URL/token/signing secret/distributed security backend) when backend mode is enabled.
- Supported secure-runtime PDF engines: `pdfshift`, `chromium`.

## Current Performance-Critical Paths

- `get_leadership_metrics`
- `get_krs_needing_checkin`
- `get_hours_by_goal`

These paths now have explicit query-count budgets and a reproducible benchmark script.

## Current Architectural Limits

- Backend API availability is a hard runtime dependency for frontend reads/writes.
- Direct DB restore is disabled by default and blocked in production; enable only for controlled non-production operations via `OKR_ENABLE_DIRECT_DB_RESTORE=true`.
- Backend-assisted Kubernetes manifests are available in `deploy/k8s/` for `okr-backend-api` and `okr-backend-worker`.

## Recommended Next Refactor Boundary

To move toward higher-concurrency internal production:

- Keep all frontend read/write contracts backend-owned (implemented) and continue tightening backend API contract/version governance.
- Preserve SQLModel domain logic while expanding backend-side query composition.
