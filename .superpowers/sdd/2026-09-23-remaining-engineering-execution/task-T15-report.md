Documentation HQ: [README](../../../README.md)

# T15 — Route and surface E2E report

## Implemented

Changed only `tests/test_e2e_playwright_spa_login_to_atlas.py` and this report.

- Added rendered content assertions for `/dashboard`, `/daily`, `/timeline`, and `/retrobox` for admin, manager, and member sessions.
- Added admin Users, Teams, Backup, and Audit tab assertions; manager Cycles-only assertions; and a direct member `/admin` denial assertion.
- Added direct-load/reload deep-link selected-state assertions for `goal_1`.
- Seeded an objective alignment edge and a closed task work log with a Persian summary in the existing per-run SQLite fixture. The database remains under the unique pytest temporary directory.
- Added rendered Inspector alignment-edge and RTL work-history assertions. RTL checks the expanded summary's computed `direction: rtl` and `text-align: right`.
- Set the worker heartbeat under the same unique temporary directory.
- Added Windows listener cleanup for the fixture's three random service ports after discovering that an npm wrapper could leave its Next.js child process running.

## Verification

- `.venv\Scripts\ruff.exe check tests/test_e2e_playwright_spa_login_to_atlas.py` — PASS.
- `.venv\Scripts\python.exe -m py_compile tests/test_e2e_playwright_spa_login_to_atlas.py` — PASS.
- Focused role-route rerun after the BFF 429 fix, with the fixture-only 10,000-request IP limit: **1 passed in 42.65s**. Admin, manager, and member completed the four route checks; post-login session checks returned 200.

  ```powershell
  $env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
  .venv\Scripts\python.exe -m pytest --basetemp=.test-artifacts/t15-role-route-rerun-20260923 -p no:cacheprovider -s -q tests/test_e2e_playwright_spa_login_to_atlas.py::test_role_route_surfaces_and_admin_access
  ```
- Full opted-in module command:

  ```powershell
  $env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
  .venv\Scripts\python.exe -m pytest --basetemp=.test-artifacts/t15-full-module-20260923 -p no:cacheprovider -v tests/test_e2e_playwright_spa_login_to_atlas.py
  ```

- Full module result: **6 passed in 124.24s** — role-route surfaces; deep-link/alignment rendering; Inspector work-history RTL; admin, manager, and member critical paths.
- Persistent run logs: `.test-artifacts/t15-full-module-20260923/playwright_spa_e2e0/`. No rate-limit 429, `SESSION_REVOKED`, or `bff_session_validation_failed` entries occurred. The only `/session/me` 401s were expected unauthenticated checks before login in fresh contexts.
- Elevated cleanup verification found no remaining listeners on fixture ports 53435 (backend), 53436 (BFF), and 53437 (SPA).

## Status

T15 is **complete locally and ready for independent review**. The rendered route, deep-link/alignment Inspector, RTL work-history, and role-critical-path acceptances pass. The fixture raises the per-IP rate-limit ceiling because this packet exercises route behavior and all simulated users share one trusted loopback IP; rate-limit behavior is verified in its own packet. Full module logs and process-cleanup evidence are retained above.

## Historical debugging incident: alignment-context API defect (resolved)

After the coordinator stopped the earlier test-owned Next.js process tree, the single alignment test was run once:

```powershell
$env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q tests/test_e2e_playwright_spa_login_to_atlas.py::test_atlas_deep_link_and_rendered_alignment
```

Result: **1 failed in 76.67s**. Direct-load `goal_1` selection survived reload, and the Inspector opened for `objective_1`. The seeded edge assertion captured four HTTP 500 responses. The Inspector rendered `Read query failed: Unexpected server error while processing read query.` The test failure now includes the per-run `backend.log` tail.

The backend HTTP logger records only the exception type. A direct reproduction against the test's isolated SQLite database, with the fixture's database-mode settings, exposed the traceback:

```text
Traceback (most recent call last):
  File "<stdin>", line 6, in <module>
  File "backend_app/main.py", line 387, in _read_query_payload
    return _read_query_payload_impl(...)
  File "backend_app/read_query_helpers.py", line 1247, in read_query_payload
    main._enum_value(getattr(edge, "alignment_type", "SUPPORTS"))
AttributeError: module 'backend_app.main' has no attribute '_enum_value'
```

The fixture database contains the expected edge (`2 -> 1`). `backend_app.main` does not expose `_enum_value`. The existing working pattern imports it directly from `src.serialization_helpers`; `backend_app/input_normalization.py` and `backend_app/response_scope_helpers.py` already use that import pattern. A read-only minimal check against the same isolated database confirmed `_enum_value(edge.alignment_type)` returns `SUPPORTS`. No backend/app code was changed in T15.

The single rerun left a listener on its unique SPA port 59419: PID 27772 (`node.exe`), launched by this fixture as `npm run dev -- --port 59419 --hostname 127.0.0.1`. `Get-CimInstance` and `taskkill /PID 27772 /T /F` both returned `Access denied`; cleanup is bounded to that test-owned process tree and requires coordinator cleanup in a context with permission.

### Alignment API follow-up

The narrow follow-up fix is complete in `backend_app/read_query_helpers.py`: the alignment serializer now imports and calls `_enum_value` from `src.serialization_helpers` instead of looking for the helper on `backend_app.main`.

TDD evidence:

- Added `tests/test_alignment_context_read.py`, which creates an authenticated reader, two persisted objectives, and a real `AlignmentEdge`, then calls `POST /v1/read/query` with `kind="alignments.context"`.
- RED before the production change: the endpoint returned HTTP 500; the backend logged `error_type=AttributeError` for the missing `main._enum_value` lookup.
- GREEN after the production change: response status was 200 and the test asserted the literal serialized edge IDs and `alignment_type: "SUPPORTS"`.
- `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q tests/test_alignment_context_read.py tests/test_alignment_dag.py tests/test_read_actor_presence.py` — **24 passed**.
- `.venv\Scripts\ruff.exe check backend_app/read_query_helpers.py tests/test_alignment_context_read.py` — **passed**; `py_compile` for both owned Python files — **passed**.
- `.venv\Scripts\mypy.exe --follow-imports=silent backend_app/read_query_helpers.py` still reports two existing diagnostics outside the edit at lines 195 (`arg-type`) and 554 (`arg-type`).
- Opted-in single browser acceptance `test_atlas_deep_link_and_rendered_alignment` — **1 passed in 56.28s**. The Inspector rendered the seeded edge after the API fix.

After that historical browser run, no listener on the previously reported port 59419 remained. Netstat showed Node listeners on ports 59418 (PID 13412) and 63118 (PID 16108), but their process start times predate that test run (15:44 and 15:26 local, respectively). Their command lines were access-restricted (`Get-CimInstance Win32_Process` returned `Access denied`), so they were not stopped because test ownership could not be established. Subsequent current full-module cleanup is verified above.

### Historical browser-process cleanup incident (resolved)

An earlier process-context run left a test-owned Next.js child on port 63119 (PID 25776); `taskkill /PID 25776 /T /F` returned `ERROR: Access denied`, and a follow-up test failed with `ERR_CONNECTION_REFUSED`. The fixture now has Windows process-tree and port-listener cleanup. The latest full-module run used elevated process context and verified all three fixture listeners had exited.
