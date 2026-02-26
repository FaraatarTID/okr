Documentation HQ: [README](../README.md)

Hybrid Frontend Streamlit Retirement Phase

Date
- 2026-02-26

Scope
- Execute Streamlit runtime retirement for active launch/deploy paths.

Completed Actions
1. Extracted shared runtime package to repo-root `src/` from `streamlit_app/src`.
2. Updated backend runtime bootstrap to require shared `src/` package (no Streamlit path fallback).
3. Switched Docker Compose defaults to SPA stack (`backend-api`, `backend-worker`, `spa-bff`, `spa-web`).
4. Removed legacy Streamlit service from active compose stack and launcher paths.
5. Updated Windows launchers and primary docs to align with SPA-only runtime.
6. Added backend-only dependency manifest (`backend_app/requirements.txt`) and backend Docker image defaults.
7. Promoted root-level Alembic assets (`alembic.ini`, `alembic/`) for shared runtime migrations.

Rollback Safety
- Rollback now targets previous SPA/backend image tags, not Streamlit runtime reactivation.
- Runtime config gate + `.env`/`secrets.toml` templates remain the rollback-safe control point.

Validation Notes
- `python -c "import backend_app.main; import backend_app.worker"` passes.
- `python -c "import src; import src.crud; import src.database"` passes.
- Backend import succeeds without `streamlit_app` path on `sys.path`.

Residual Follow-up
1. Gradually migrate historical docs that still describe Streamlit-era architecture to SPA-first equivalents.
2. Remove legacy `streamlit_app/` code tree once remaining non-runtime references are archived.
