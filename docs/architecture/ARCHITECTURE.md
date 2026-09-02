# Architecture

Documentation HQ: [README](../../README.md)

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
- In Supabase API mode, the Check-In ritual read uses the consolidated `ritual.snapshot` kind: a single `fn_ritual_snapshot` RPC (migration `y2d3e4f5a6b7`) returns key results, weekly plan, retrospectives, work logs, and experiments in one round trip, with automatic fallback to the legacy concurrent fan-out only when the RPC is missing (SQLSTATE 42883).

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
  - Each customer deployment has its own application environment and dedicated Supabase PostgreSQL database.
  - Customer isolation is provided by the deployment and database boundary; shared-database multi-tenancy is not a supported product model.
  - Connection policy expects transaction pooler endpoint (`:6543`).
  - Runtime DSN should use a least-privilege app user (not `postgres`) except explicit break-glass overrides.
  - Postgres engine defaults to `NullPool` in app runtimes to align with Supabase PgBouncer transaction pooling.
- Data-access mode resolution (`backend_app/data_access_mode.py`):
  - In the `saas` deployment profile, only `OKR_DATA_ACCESS_MODE=database` is valid; startup rejects every other value.
  - `OKR_DATA_ACCESS_MODE=supabase_api` is an alpha/self-hosted compatibility mode, not a SaaS architecture option.
  - Otherwise TCP is primary; a cached probe re-checks connectivity every ~5 minutes.
  - TCP unreachable + Supabase credentials present → reads fall back to the HTTPS API automatically (warn-once per outage); mutations never silently fail over (double-write risk) and fail closed.
  - `notify_tcp_db_failure()` invalidates the probe cache so traffic returns to TCP quickly after recovery.
- Transport resilience (`src/services/supabase_api_mode_transport.py`, HTTPS path):
  - Process-wide concurrency semaphore (default 4; `OKR_SUPABASE_MAX_CONCURRENCY`) caps in-flight upstream calls.
  - Circuit breaker opens after consecutive transport failures (default 5; `OKR_SUPABASE_BREAKER_THRESHOLD`) and fails fast for a cooldown (default 30s; `OKR_SUPABASE_BREAKER_COOLDOWN_S`), then half-open probes.
  - Cached process-local HTTP client is closed on app shutdown via the FastAPI lifespan.
- Service boundary:
  - `backend-api` authenticates service calls using `OKR_BACKEND_SERVICE_TOKEN`.
  - Optional cryptographic request signing (`OKR_BACKEND_SIGNING_SECRET`) enforces signed/replay-protected internal calls.
  - Key rotation: when `OKR_BACKEND_SIGNING_KEY_ID` is advertised, callers must send `x-okr-key-id`; unknown IDs are rejected. During rotation, `OKR_BACKEND_SIGNING_SECRET_PREVIOUS` keeps old-secret signatures valid (overlap window). See runbook in `DEPLOYMENT.md`; tests in `tests/test_signing_key_rotation.py`.
  - IP-based rate limiting protects API endpoints. When `spa-bff` proxies requests with a valid service token, the backend uses `x-forwarded-for` for per-user rate limiting instead of the proxy IP.
- Network boundary:
  - Public ingress should expose only reverse proxy/app paths.
  - `backend-api` should remain private (loopback/internal bind in compose by default).
- Data egress boundary:
  - AI calls are policy-gated by `ALLOW_EXTERNAL_AI`.
  - `AI_PROVIDER=openai_compatible` supports internal/self-hosted gateways.
- Observability boundary:
  - All backend services use structured Python logging (`logging.getLogger(__name__)`).
  - Error handlers use `logger.exception()` to include tracebacks in logs.
  - Fail-open fallback paths log at `warning` level with `exc_info=True` for debugging.
  - Audit events are persisted to `AuditEvent` table with correlation/request IDs.

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
  - alignment edges (objective↔objective) and cross-hierarchy links (objective↔goal, objective↔KR)
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
- "+" button in Focus Map creates the direct child type (Goal→Objective, Objective→KR, KR→Task).
- "Create Goal" button in Focus Map creates a top-level Goal.

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
- The Check-In page loads its data via the consolidated `ritual.snapshot` read kind (`fn_ritual_snapshot` RPC in Supabase API mode), reducing latency versus per-section queries.

3. Progress and scoring flow

- Task progress is auto-computed: `total_time_spent / estimated_minutes * 100` (can exceed 100%).
- KR progress is set via check-ins or AI Sync.
- Goal/Objective progress is a computed rollup from child KRs — not user-set.
- Deadline health is computed via `get_deadline_status` (supports both ORM objects and dict payloads).
- Leadership rollups aggregate task progress, deadline status, check-in freshness, confidence, and risk.

4. Permission / sharing flow

- Mutating actions call `_authorize_goal_mutation`.
- Owner, manager-of-owner, and admin paths are enforced before changes are committed.
- Read-sensitive node retrieval can be actor-scoped via `get_node(..., actor_username=...)`.
- AI node analysis (`analyze_node`) uses actor-scoped read path and includes alignment context (edges + cross-hierarchy links) in the prompt.
  - SaaS DB access uses direct Postgres through the transaction pooler. Alpha/self-hosted compatibility deployments may use the centralized HTTPS mode resolver for reads, but that path is excluded from customer production deployments.

5. Alignment flow

- `AlignmentEdge`: directed links between objectives (SUPPORTS/CONTRIBUTES types).
- `ObjectiveAlignmentLink`: cross-hierarchy links between an objective and a Goal (parent) or Key Result (child).
- Alignment context (`alignments.context` read query) returns parents, children, all objectives, edges, available goals, available KRs, and existing cross-hierarchy links.
- Dropdown filtering excludes already-linked entities (via FK hierarchy and alignment links).
- Cycle detection prevents circular alignment dependencies.

6. Async job flow

- `run_job_and_wait` submits to `backend-api` when backend mode is enabled.
- Job lifecycle: `pending -> running -> succeeded|failed|cancelled`.
- Worker writes result/error payloads into `async_job`.
- Frontend reads job state and surfaces final output.
- Job submission is guarded by per-user/per-team quotas and idempotency keys in backend API.
- In PostgreSQL runtimes, worker claim path uses `FOR UPDATE SKIP LOCKED` semantics to reduce queue-head contention across concurrent workers.
- Worker resiliency guardrails include capped attempts, terminal handling for non-retryable payload failures, and bounded error-text persistence.
- Dead-letter visibility: exhausted FAILED jobs are listed by `GET /v1/jobs/dead` (admin) and retryable via `POST /v1/jobs/{id}/retry`; `/healthz` reports a `dead_jobs` count.

## Invariants and Guardrails

### OKR Methodology Rules
- Goals and Objectives are time-bounded by the OKR cycle, NOT by individual deadlines.
- Only Key Results have measurable progress (measured through check-in sessions).
- Only Tasks have deadlines.
- Progress on Goals/Objectives is a computed rollup from child KRs — it is not user-set.
- Task progress is auto-computed from `total_time_spent / estimated_minutes * 100` (can exceed 100%).
- AI analysis provides advisory insights; KR progress is entered exclusively by users via check-in sessions.

### Technical Guardrails

- Goal ownership is anchored on `goal.owner_id`.
- Mutations require `actor_username` for goal-scoped entities.
- DB constraints enforce non-negative progress and durations, and single open work log per task. Task progress can exceed 100% (auto-computed from time tracking).
- Cycles are per-owner: partial unique index `ux_cycle_owner_active` enforces at most one active cycle per `owner_manager_id` (admin-owned cycles act as global cycles visible to everyone). Managers see only their own + admin-owned cycles; members resolve to their manager's active cycle, falling back to an active global cycle. Managers cannot mutate admin-owned cycles (activate/deactivate/delete/ownership changes are admin-only).
- Hot-path query budgets are tested in `tests/test_performance_hotpaths.py` to prevent N+1 regressions.
- The Atlas hierarchy read is set-based across goals, objectives, key results,
  and tasks; do not introduce lazy ORM traversal without a query-count test.
- Ritual mode consumes experiments from the consolidated snapshot instead of
  issuing one follow-up request per key result.
- The Atlas snapshot starts immediately without an artificial 200 ms delay and
  excludes raw AI analysis from non-inspector views to limit payload size.
- These code-level safeguards do not replace browser waterfall and backend
  tracing; the remaining performance gate is measured end-to-end latency.
- Runtime preflight defaults to strict (`OKR_STRICT_RUNTIME_PREFLIGHT=true`) for fail-fast misconfiguration detection.
- Runtime preflight validates backend production wiring (API URL/token/signing secret/distributed security backend) when backend mode is enabled.
- Supported secure-runtime PDF engines: `pdfshift`, `chromium`.

## Current Performance-Critical Paths

- `get_leadership_metrics`
- `get_krs_needing_checkin`
- `get_hours_by_goal`

These paths now have explicit query-count budgets and a reproducible benchmark script.

## Contract Governance

- The backend OpenAPI schema (49 paths, OpenAPI 3.1) is exported to `spa-web/src/lib/api/openapi.json` via `scripts/export_openapi.py`.
- CI runs an OpenAPI drift gate (`scripts/check_openapi_drift.py`): any backend schema change without regenerated frontend types fails the build.
- TypeScript types are generated from the artifact via `just generate-api`, which refreshes both `spa-web/src/lib/api/generated/schema.d.ts` and `spa-bff/src/generated/backend-schema.d.ts`; adopt them incrementally (see `spa-web/src/lib/api/backend-schema.ts` for the pattern).
- Mutation-route coverage is enforced by `tests/test_backend_mutation_auth_matrix.py`: every backend mutation route must appear in both the test matrix and the BFF allowlist.

## Contributor Decision Guide

**Choosing a data path:**
1. SaaS default: use CRUD/SQLAlchemy (TCP) through the transaction pooler. Do not set `OKR_DATA_ACCESS_MODE` to an HTTPS mode for SaaS.
2. Reads work identically in both modes — dispatch is centralized in `backend_app/data_access_mode.py::resolve_read_mode()`; do not branch on mode ad hoc.
3. Mutations always run on the active primary path and fail closed; never add silent fallbacks.

**Adding a read kind (checklist):**
1. Implement dispatch in `backend_app/read_query_helpers.py` (+ scope validation via `_validate_supabase_read_scope`).
2. Add the HTTPS-mode query in `src/services/supabase_api_mode_read.py`.
3. Register the kind in the allowed-kinds list and README's kinds enumeration.
4. Add tests covering scope rejection + payload mapping (see `tests/test_ritual_snapshot_rpc.py` for the pattern).
5. Regenerate all API artifacts: `just generate-api`.

**Adding a mutation route (checklist):**
1. Add handler + route in `backend_app/routers/*_routes.py` behind `require_service_access`.
2. Add the route to `spa-bff/src/allowlist.ts` (path template + regex).
3. Add it to the matrix in `tests/test_backend_mutation_auth_matrix.py` — CI fails if either allowlist or matrix misses it.
4. Add negative tests (non-owner/member denial paths).
5. Regenerate OpenAPI types with `just generate-api`.

## Current Architectural Limits

- Backend API availability is a hard runtime dependency for frontend reads/writes.
- Direct DB restore is disabled by default and blocked in production; enable only for controlled non-production operations via `OKR_ENABLE_DIRECT_DB_RESTORE=true`.
- Backend-assisted Kubernetes manifests are available in `deploy/k8s/` for `okr-backend-api` and `okr-backend-worker`.

## Forward-Looking Work

Active production-readiness work is tracked in
[ARCHITECTURE_BACKLOG.md](ARCHITECTURE_BACKLOG.md). Shared-database
multi-tenancy and RLS-based tenant isolation are permanently out of scope;
customer isolation is provided by dedicated deployments and databases.
Superseded status and worklog records are preserved in
[docs/archive/architecture-2026-08-31/](../archive/architecture-2026-08-31/).
Process definition: [docs/ARCHITECTURE_DELIVERY_SYSTEM.md](../ARCHITECTURE_DELIVERY_SYSTEM.md).

