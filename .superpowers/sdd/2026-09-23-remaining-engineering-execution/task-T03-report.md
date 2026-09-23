# T03 — Actor-presence audit implementation report

Status: implementation complete, awaiting independent task review. No production or generated files changed.

## Reserved and changed files

- `tests/test_read_actor_presence.py` — backend HTTP negative, mismatch, and positive cases for every named kind.
- `spa-bff/test/read_actor_presence.test.ts` — BFF missing-session refusal and session-actor forwarding for every named kind.
- `.superpowers/sdd/2026-09-23-remaining-engineering-execution/task-T03-report.md` — this report.
- `.superpowers/sdd/2026-09-23-remaining-engineering-execution/task-T03-snapshot.md` — review snapshot.

No T07 script/CI paths, shared progress ledger, T02 visibility predicates, route contract, OpenAPI, allowlist, or generated artifact was edited. No Git writes were attempted.

## Seven-kind request-path matrix

All seven share public `POST /api/backend/v1/read/query` in `spa-bff/src/server.ts:500-611`. `spa-bff/src/route-policy.json:255-260` and `spa-bff/src/allowlist.ts:48` mark its backend operation `actorRequired: true`; the BFF returns `MISSING_SESSION` 401 before `proxyToBackend` when session verification fails (`server.ts:528-543`). It obtains `actor` from the verified session and `proxyToBackend` writes `X-OKR-Actor` (`spa-bff/src/proxy.ts:128-129`). The backend route in `backend_app/routers/platform_routes.py:179-218` resolves header/payload actors before `_read_query_payload`; `backend_app/security.py:321-341` refuses both absent (400) or mismatched (403). `backend_app/read_query_helpers.py:216-290,346-384` resolves actor scope before TCP/HTTPS dispatch. The HTTPS owner precheck is `:133-177`, and its seven kinds match this matrix.

| Kind | Request params | TCP downstream | HTTPS downstream | Test evidence |
| --- | --- | --- | --- | --- |
| `node.get` | `node_id`, `node_type` | `read_query_helpers.py:757-769` → real `get_node(..., actor_username=actor)` → `src/crud_query_helpers.py:20-98` | Owner precheck followed by `supabase_api_mode_read.py:471-490` | Missing BFF session 401; absent backend actor 400; mismatched actor 403; valid actor reaches real scoped Task. The positive test isolates only the detached serializer after `get_node`. |
| `node.detect_type` | `node_id` | `read_query_helpers.py:771-777` → ordered `get_node(..., actor_username=actor)` probes | Owner precheck followed by `supabase_api_mode_read.py:451-470` | Same three refusals; valid actor resolves real, uniquely numbered Task as `TASK`. |
| `work_logs.by_task` | `task_id` | `read_query_helpers.py:899-921` → real scoped Task `get_node` | Owner precheck followed by `supabase_api_mode_read.py:668-681` | Same three refusals; valid actor returns `work_logs` from real Task. |
| `experiments.for_kr` | `key_result_id` | `read_query_helpers.py:981-1003` → `list_experiments_for_kr`, which calls `_authorize_node_scoped_access` in `src/crud_experiment_helpers.py:137-156` | Owner precheck followed by `supabase_api_mode_read.py:860-875` | Same three refusals; valid actor gets one real experiment. This TCP branch does not call `get_node` directly; its own node authorization uses the actor. |
| `experiments.active_for_kr` | `key_result_id` | `read_query_helpers.py:959-979` → `get_active_experiments_for_kr`, which calls `_authorize_node_scoped_access` in `src/crud_experiment_helpers.py:158-180` | Owner precheck followed by `supabase_api_mode_read.py:843-859` | Same three refusals; valid actor gets one running experiment. This TCP branch also uses direct scoped authorization. |
| `alignments.context` | `objective_id` | `read_query_helpers.py:1105-1120` → real Objective `get_node` before alignment data queries | Owner precheck followed by `supabase_api_mode_read.py:954-1035` | Same three refusals; valid actor reaches context and returns `parents` section. |
| `mindmap.root` | `node_id`, `node_type` | `read_query_helpers.py:1284-1328` → real `get_node` before tree serialization | Owner precheck followed by `supabase_api_mode_read.py:1139-1263` | Same three refusals; valid actor returns a real Task node. |

The backend negative controls use seeded, existing IDs and call the actual FastAPI route. No actor means the route returns 400 before scope or data access. A mismatched payload actor returns 403 before scope resolution. The BFF negative controls send a forged payload actor with no session and assert `fetchFn` was never called. Positive backend controls use real SQLite rows and the real scope resolver; the BFF controls verify the session actor is the forwarded header for each kind. Existing `tests/test_crud_authorization.py` covers `get_node`'s `UnscopedNodeReadError` and authorized/unauthorized node access.

## Separate defect discovered during positive controls

Unpatched `node.get` returned HTTP 500 with `DetachedInstanceError` for both a real Goal and a real Task **after** actor resolution and `get_node` authorization. The Goal traceback identifies `backend_app/response_scope_helpers.py:187`: `_serialize_key_result` lazily reads `KeyResult.tasks` from a detached instance returned by the Goal `get_node` query. The Task also fails in its full serializer; I did not patch production read payload code within this actor-presence packet. In only the `node.get` positive test, `_serialize_node_for_type` is replaced after real scoped `get_node` with a minimal Task payload; the seam asserts that the received value is a real `Task` with the requested ID and includes the owner ID for the subsequent scope guard. This preserves actor-path proof and leaves payload repair to the read-path owner (T02 or a scoped follow-up). This means T03 does not assert the full unpatched `node.get` response succeeds.

## Verification

- `.venv\\Scripts\\pytest.exe -q tests/test_read_actor_presence.py tests/test_crud_authorization.py -p no:cacheprovider`: **36 passed**, 1 pre-existing Starlette/httpx deprecation warning.
- `npm run test --workspace spa-bff -- read_actor_presence.test.ts allowlist.test.ts`: **23 passed** in two files.
- `npm run typecheck --workspace spa-bff`: pass.
- `.venv\\Scripts\\ruff.exe check tests/test_read_actor_presence.py`: pass.

No owner or external gate blocks this actor-presence audit. The known `node.get` payload defect is a separate follow-up before claiming that full Goal/Task reads work.
