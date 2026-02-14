# Architecture

Documentation HQ: [README](README.md)

## System Overview

This repository is a Streamlit-based OKR product with a SQLModel persistence layer on Supabase PostgreSQL.

- UI entrypoint: `streamlit_app/app.py`
- UI composition: `streamlit_app/src/ui/components.py`, `streamlit_app/src/ui/dialogs.py`, `streamlit_app/src/ui/visualizations.py`
  - Primary hierarchy UX: Atlas 3-pane workspace (Navigator / Workspace / Inspector)
  - Compatibility UX: Classic drill-down cards with breadcrumb navigation
- Domain/data operations: `streamlit_app/src/crud.py`
- Extracted domain modules:
  - `streamlit_app/src/domain/authorization.py` (ownership/RBAC predicates + authorizers)
  - `streamlit_app/src/domain/analytics.py` (hot-path analytics/reporting queries)
- Persistence: `streamlit_app/src/database.py`, `streamlit_app/src/models.py`, Alembic migrations in `streamlit_app/alembic/`
- External integrations: `streamlit_app/src/services/ai_service.py`, `streamlit_app/src/services/pdf_service.py`
- Shared business helpers: `streamlit_app/utils/deadline_utils.py`

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

4. Integration boundary (`services/*`)
- Owns AI analysis and PDF/report output.
- Should not contain core authorization logic.

## Critical Request/Data Flows

1. Objective / KR / Task creation
- UI dialog submits to `create_goal` / `create_objective` / `create_key_result` / `create_task`.
- CRUD validates actor permissions using ancestor goal ownership.
- DB commit persists node on Supabase PostgreSQL.

1b. Hierarchy navigation flow (Atlas mode)
- `render_level` dispatches to `render_atlas_workspace` when `workspace_mode=Atlas`.
- Left pane builds a typed-reference tree for active cycle scope and role-aware owner filters.
- Center pane renders selected node context, filtered/sorted children, and inline add actions.
- Right pane mounts `render_inspector_content(..., show_close=False)` as persistent inspector.

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

## Invariants and Guardrails

- Goal ownership is anchored on `goal.owner_id`.
- Mutations require `actor_username` for goal-scoped entities.
- DB constraints enforce progress ranges, non-negative durations, and single open work log per task.
- Hot-path query budgets are tested in `test_performance_hotpaths.py` to prevent N+1 regressions.

## Current Performance-Critical Paths

- `get_leadership_metrics`
- `get_krs_needing_checkin`
- `get_hours_by_goal`

These paths now have explicit query-count budgets and a reproducible benchmark script:
- `streamlit_app/scripts/perf_hotpaths.py`
