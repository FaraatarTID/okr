Documentation HQ: [README](README.md)

# Codebase Map

Maintainer-focused map for the primary files and helper boundaries.

## How To Use This

- Start here before changing any high-traffic file.
- Use this map to decide _where_ code should live and _which tests_ should be updated.
- Keep this file updated whenever a major module responsibility changes.

## Runtime Flow (At a Glance)

1. `spa-web/` provides the primary Next.js UI.
2. `spa-bff/` handles browser-facing API boundary, auth, and proxying.
3. `backend_app/main.py` (API) -> `backend_app/jobs.py` -> `backend_app/worker.py` own mutations, reads, and async work.

## Primary File Ownership Map

| File                                             | Responsibility                                       | Keep Here                                               | Move To                         | Key Dependencies                                             | Key Tests                                                                                                                                                                               |
| ------------------------------------------------ | ---------------------------------------------------- | ------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend_app/main.py`                            | Internal backend API for secure mutations/jobs       | Request validation, auth gate, endpoint orchestration   | Core CRUD rules                 | `backend_app.security.py`, `backend_app/jobs.py`, `src.crud` | backend API tests, security/rate-limit tests                                                                                                                                            |
| `backend_app/worker.py`                          | Async job worker loop                                | Claim/run/mark job lifecycle                            | Job business semantics          | `backend_app/job_runner.py`, `backend_app/jobs.py`           | worker/job lifecycle tests                                                                                                                                                              |

## CRUD Helper Spine

- Primary slices:
  - `crud_auth_helpers.py`
  - `crud_create_helpers.py`
  - `crud_update_helpers.py`
  - `crud_delete_helpers.py`
  - `crud_query_helpers.py`
  - `crud_data_helpers.py`
  - `crud_progress_helpers.py`
  - `crud_timer_helpers.py`
  - `crud_cycle_helpers.py`
  - `crud_checkin_helpers.py`
  - `crud_experiment_helpers.py`
  - `crud_team_helpers.py`
  - `crud_alignment_helpers.py`
  - `crud_reflection_helpers.py`

## Change Playbooks

### Add/Change CRUD mutation

1. Implement in `crud_*_helpers.py`.
2. Wire through `crud.py` with backward-compatible signature.
3. Validate authorization path and backend-proxy behavior.
4. Update authorization + regression tests.

### Add backend API endpoint

1. Add schema in `backend_app/schemas.py`.
2. Add endpoint in `backend_app/main.py`.
3. Reuse `src.crud` public API (do not bypass policy in ad-hoc SQL).
4. Add API test plus failure-path coverage.

## Maintainer Guardrails

- Do not place new business logic directly in `crud.py`.
- Preserve compatibility exports used by monkeypatch-based tests.

## Suggested Ownership Convention

- Coordinator/facade files should primarily change for:
  - wiring updates
  - compatibility surface updates
  - cache boundary changes
- Feature helper files should change for behavior.
