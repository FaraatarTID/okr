Documentation HQ: [README](../../../README.md)

# T02 snapshot

Reserved code/test files changed:

- `backend_app/response_scope_helpers.py`
- `backend_app/read_query_helpers.py` (task serialization call only)
- `src/services/supabase_api_mode_read.py`
- `tests/test_dual_mode_parity.py`
- `tests/test_supabase_api_mode_read.py`

Other packet-owned artifacts:

- `task-T02-report.md`
- `task-T02-snapshot.md`

Acceptance checkpoints:

- [x] Decision implemented: non-admin sees task if parent goal owner is in `scope.owner_ids` OR task assignee is in `scope.owner_ids`.
- [x] TCP injected attribute failure is explicit HTTP 500 with sanitized detail; no broad silent row loss.
- [x] HTTPS nested fast path and relationship fallback include assigned tasks whose parent goal owner is out of scope, while staying cycle-bounded.
- [x] Explicit foreign-goal/out-of-scope-assignee exclusion, owner-visible control, in-scope assignee with foreign goal, and admin positive control.
- [x] Assignee-only task context is reduced to the parent IDs and display titles needed by AtlasShell: key result, objective, and goal.
- [x] Real PostgREST transport test proves a fallback task query status >= 400 raises a sanitized explicit error; `krs.needing_checkin` includes foreign-owner and inactive candidate exclusions.
- [x] Focused tests, scoped typing, Ruff lint and format checks passed.
- [x] Independent T02 review PASS; see `task-T02-review.md`.
- [x] Cross-mode restricted payload equality covers all six F3 kinds in `tests/test_dual_mode_parity.py`.
- [ ] Repository-wide mypy is not clean: two unrelated diagnostics remain in `backend_app/read_query_helpers.py`; that file is outside this packet's reserved surface.
