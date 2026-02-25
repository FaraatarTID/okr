# Architecture

Documentation HQ: [README](README.md)

Learning Loop specific architecture contract (EN+FA, canonical): [docs/LEARNING_LOOP_ARCHITECTURE.md](docs/LEARNING_LOOP_ARCHITECTURE.md)

Maintainer file ownership and change map: [CODEBASE_MAP.md](CODEBASE_MAP.md)

## System Overview

This repository is a Streamlit-based OKR product with a SQLModel persistence layer on Supabase PostgreSQL.

Current runtime topology has two profiles:

- `Backend-segregated mode` (default):
  - Streamlit UI renders pages and handles session UX.
  - Synchronous reads and mutations route through internal backend services:
    - `backend-api` (FastAPI control plane)
    - `backend-worker` (async execution plane for heavy jobs)
  - Jobs are persisted in `async_job` table and processed out-of-band.
- `Embedded mode` (Streamlit Cloud / auto):
  - Used when `OKR_BACKEND_API_URL` is `"auto"`.
  - Streamlit frontend automatically launches `backend-api` as a background subprocess via `backend_launcher.py`.
  - Provides a single-container deployment experience while maintaining backend-first integrity.

- UI entrypoint: `streamlit_app/app.py`
- UI composition: `streamlit_app/src/ui/components.py`, `streamlit_app/src/ui/dialogs.py`, `streamlit_app/src/ui/visualizations.py`
  - Primary hierarchy UX: Atlas focus-first workspace (`Focus Map` + `Inspector`)
- Domain/data operations: `streamlit_app/src/crud.py`
- Extracted domain modules:
  - `streamlit_app/src/domain/authorization.py` (ownership/RBAC predicates + authorizers)
  - `streamlit_app/src/domain/analytics.py` (hot-path analytics/reporting queries)
- Persistence: `streamlit_app/src/database.py`, `streamlit_app/src/models.py`, Alembic migrations in `streamlit_app/alembic/`
- External integrations: `streamlit_app/src/services/ai_service.py`, `streamlit_app/src/services/pdf_service.py`
- Shared business helpers: `streamlit_app/src/utils/deadline_utils.py`
- Backend services & launcher:
  - `streamlit_app/src/services/backend_launcher.py` (Embedded process manager)
  - `backend_app/main.py`, `backend_app/worker.py`, `backend_app/jobs.py`

## Runtime Topology

Primary data/control flow in backend-segregated mode:

1. UI and session:

- Browser -> Streamlit (`okr` service).
- Streamlit handles page rendering, state, and role-aware UX.

2. Synchronous domain mutations:

- Streamlit -> `backend-api` mutation endpoints -> CRUD (`src/crud.py`) -> Supabase PostgreSQL.
- Default behavior (all environments): fail closed with explicit user-facing error when backend transport fails.
- Scope (frontend write paths): Goal/Objective/KeyResult/Task CRUD, timer start/stop, user/cycle/team admin mutations, Learning Loop mutations (check-ins/experiments/retrospectives/weekly plans/outcomes), alignment mutations, and work-log deletes.

3. Synchronous read/query paths:

- Streamlit -> `backend-api` read endpoints -> CRUD (`src/crud.py`) -> Supabase PostgreSQL.
- Atlas snapshot/runtime reads and leadership read paths are backend-served in runtime mode.

4. Async heavy workflows:

- Streamlit -> `backend-api` (`/v1/jobs`) with `OKR_BACKEND_SERVICE_TOKEN`.
- `backend-api` enqueues durable jobs in `async_job`.
- `backend-worker` claims and executes jobs (`ai.generate_json`, `pdf.weekly`).
- Streamlit polls job status and renders result.

5. Timer routing:

- Streamlit timer service -> `backend-api` (`/v1/timer/start|stop`).
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

- Owns Streamlit rendering and session state orchestration.
- Calls CRUD/service functions; does not own database transactions.

2. Domain boundary (`crud.py` facade + `src/domain/*` + `deadline_utils.py`)

- Owns business rules for:
  - CRUD and hierarchy traversal
  - authorization checks (owner/manager/admin)
  - check-ins, reports, leadership metrics, timer semantics
  - deadline health/status logic
- Keeps rules testable without Streamlit runtime.
- `crud.py` remains the compatibility API used by UI/tests, while domain modules hold focused logic.

3. Persistence boundary (`database.py`, `models.py`, migrations)

- Owns connection lifecycle, schema, constraints, and indexes.
- Guarantees FK integrity, check constraints, and migration-driven schema updates.
- Manages `LifecycleState` transitions and persistence.

4. Integration boundary (`services/*` + `backend_app/*`)

- Owns AI analysis and PDF/report output.
- Should not contain core authorization logic.
- Backend API/worker isolate heavy operations from Streamlit request reruns.
- **Migration Ownership**: In Embedded mode, the frontend skips migrations to avoid database lock contention; the backend subprocess is the sole owner of `alembic upgrade`.

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

- `render_level` dispatches to `render_atlas_workspace` when `workspace_mode=Atlas`.
- Top command bar handles quick jump and role-aware scope controls.
- Focus selection and timer commitment are consolidated inside `Focus Map` to avoid duplicated surfaces.
- Workspace uses two surfaces:
  - `Focus Map`: first-glance clickable treemap + urgency legend + ranked focus candidates + commit spotlight
    - `Commit Spotlight`: single dominant commit action with sprint presets (`25m`, `50m`, `Custom`)
  - `Inspector`: deep edit/read context for selected node

## Atlas UX Architecture (v2)

Interaction model is intentionally split into control-plane and work-plane:

1. Control-plane: Focus Map Commit Loop

- Focus selection and sprint control happen in one place (`Focus Map`).
- Primary timer commitment happens in `Commit Spotlight`.
- Focused task state is sticky across tab changes.
- Human-first prompts and status chips provide instant context without metric overload.
- `Suggested Next` ranks by: running session, needs-care urgency, ownership/actionability, then progress.

2. Work-plane: Progressive disclosure

- `Focus Map` is the first-glance visual overview for focus choice.
- `Focus Map` encodes urgency with explicit visual semantics while presenting a simplified human label (`Needs care` / `On track` / `Complete`).
- Treemap urgency is intentionally grouped into a coherent `Needs care` tone to avoid visual overload.
- Map key semantics are split for clarity:
  - tile fill colors represent status (`Needs care` / `On track` / `Complete`)
  - outline/ring states represent navigation context (`Focused task` / `Selected node` / `Path context`)
- `Focus Map` defaults to full scope lens and supports branch lens for local drill-in.
- Treemap click handling uses `streamlit-plotly-events` as primary click capture with Streamlit selection fallback, normalizing payload shape differences across runtimes.
- `Inspector` is optimized for depth (details and edits).

3. State contracts

- `atlas_selected_ref`: single source of truth for current node context.
- `atlas_focus_task_ref`: explicit focus target for timer operations.
- A map click must update `atlas_selected_ref`; navigation path and `Inspector` are derived from that shared selected ref.
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
- UI reads job state and surfaces final output.
- Job submission is guarded by per-user/per-team quotas and idempotency keys in backend API.
- In PostgreSQL runtimes, worker claim path uses `FOR UPDATE SKIP LOCKED` semantics to reduce queue-head contention across concurrent workers.
- Worker resiliency guardrails include capped attempts, terminal handling for non-retryable payload failures, and bounded error-text persistence.

## Invariants and Guardrails

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

These paths now have explicit query-count budgets and a reproducible benchmark script:

- `streamlit_app/scripts/perf_hotpaths.py`

## Current Architectural Limits

- Streamlit rerun model still governs UI interaction cost and concurrency.
- Backend API availability is now a hard runtime dependency for frontend reads/writes.
- Direct Streamlit DB restore is disabled by default and blocked in production; enable only for controlled non-production operations via `OKR_ENABLE_DIRECT_DB_RESTORE=true`.
- Backend-assisted Kubernetes manifests are available in `deploy/k8s/` for `okr-streamlit`, `okr-backend-api`, and `okr-backend-worker`.

## Recommended Next Refactor Boundary

To move toward higher-concurrency internal production:

- Keep all frontend read/write contracts backend-owned (implemented) and continue tightening backend API contract/version governance.
- Keep Streamlit as presentation/workflow shell.
- Preserve SQLModel domain logic while expanding backend-side query composition to reduce UI rerun pressure.

