# Architecture

Documentation HQ: [README](README.md)

Learning Loop specific architecture contract (EN+FA, canonical): [docs/architecture.md](docs/architecture.md)

## System Overview

This repository is a Streamlit-based OKR product with a SQLModel persistence layer on Supabase PostgreSQL.

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

4. Integration boundary (`services/*`)

- Owns AI analysis and PDF/report output.
- Should not contain core authorization logic.

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

- UI weekly ritual submits `create_check_in`.
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

## Invariants and Guardrails

- Goal ownership is anchored on `goal.owner_id`.
- Mutations require `actor_username` for goal-scoped entities.
- DB constraints enforce progress ranges, non-negative durations, and single open work log per task.
- Hot-path query budgets are tested in `tests/test_performance_hotpaths.py` to prevent N+1 regressions.

## Current Performance-Critical Paths

- `get_leadership_metrics`
- `get_krs_needing_checkin`
- `get_hours_by_goal`

These paths now have explicit query-count budgets and a reproducible benchmark script:

- `streamlit_app/scripts/perf_hotpaths.py`
