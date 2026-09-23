Documentation HQ: [README](../../../README.md)

# T02 — Read-path payload parity report

Status: complete locally after independent review PASS.

## Changes

- TCP task visibility evaluation now implements the approved `goal owner in scope OR assignee in scope` rule. Admins retain the all-task fast path. If an ORM attribute/relation raises during a non-admin check, TCP logs the traceback server-side and raises HTTP 500 with the fixed detail `Unable to evaluate task visibility.` rather than dropping that row.
- HTTPS/PostgREST `tasks.by_cycle` now loads cycle goals rather than only owned goals. It keeps the candidate query bounded to the requested cycle, then applies the same owner-or-assignee union before returning rows. The hierarchy-walk fallback uses the same cycle-wide candidates and visibility rule. This includes an in-scope assignee's task even when the cycle contains no owned goal, while excluding foreign-goal tasks assigned outside scope.
- PostgREST's [resource embedding documentation](https://docs.postgrest.org/en/v13/references/api/resource_embedding.html#or-filtering-across-embedded-resources) describes cross-resource OR through filtered embedded resources and `not.is.null`. Rather than rely on that cross-resource OR/empty-embed behavior for this mixed nested-relation/top-level-column predicate, the code filters the cycle-bounded result in-process before response; relationship evaluation failures raise a fixed, sanitized `ValueError`. No exception message is passed through.
- Expanded task and cycle regressions. The cycle test now actually resolves the manager fixture scope and models `cycles.active` as active-only; this corrected a vacuous test setup exposed when the previously unused `scope` assignment was fixed. The dual-mode suite now compares restricted payloads for all six F3 kinds: `cycles.all`, `cycles.active`, `krs.by_cycle`, `tasks.by_cycle`, `krs.needing_checkin`, and `experiments.for_retro_window`.
- Applied the user's disclosure decision at the serialization boundary: an assignee-visible task whose parent goal owner is outside scope includes only the parent IDs and display titles needed by the UI: `key_result { id, title, objective { id, title, goal { id, title } } }`. It omits parent descriptions, scores, reflections, owner IDs, creators, timestamps, tags, and other metadata. Owner-visible and admin task rows keep the normal serialized parent data. `AtlasShell.tsx` reads the key result, objective, and goal titles for task context; no other parent fields are needed for that display.
- The hierarchy-walk fallback selects the goal, objective, and key-result titles as well as IDs, so assignee-only context has the required display names even when PostgREST embedding is unavailable. A regression asserts the selected columns and the three returned titles.
- The database response path re-evaluates parent ownership when selecting full versus minimal parent context. That repeat evaluation now also logs server-side and raises the same fixed HTTP 500 if a relation fails, instead of allowing a raw ORM exception to escape.
- Replaced the mocked `_serialize_task` in the task dual-mode parity case with the actual serializer. The RED run exposed the TCP/HTTPS nested context mismatch; after the service normalizes PostgREST relations and applies the minimal-context rule, the full task payloads compare equal. The test also asserts the exact minimal shape and confirms sensitive parent fields are absent.
- Added an end-to-end service test for a real PostgREST task query failure. It drives `read_query_via_supabase_api` through the transport request function, forces the nested task query to fall back, then returns HTTP 503 from the fallback task request. The service raises `Supabase API error (tasks.by_cycle/task): 503` and the private response body is absent from the error.
- Strengthened `krs.needing_checkin` behavioral fixtures with foreign-owner goals, inactive candidates under an in-scope objective, and active candidates under an out-of-cycle objective. Only the active key result under the requested user's in-scope goal appears in the matching TCP and HTTPS payloads.

## F3 negative-filter evidence

- `cycles.all` / `cycles.active`: `test_cycles_are_row_filtered_identically_in_both_modes` compares the restricted result for manager and member modes and asserts the foreign cycle is absent.
- `krs.by_cycle`: `tests/test_supabase_api_mode_read_krs_optimization.py` covers owner-goal narrowing, no-scope empty result, cycle-vs-goal ID, and fallback.
- `tasks.by_cycle`: new fast, fallback, no-owned-goal, admin-control, owner, assignee, and foreign-row cases cover the visibility predicate and cycle restriction.
- `krs.needing_checkin`: parity fixtures include a foreign owner's goal and inactive/out-of-cycle key-result candidates; the service assertions verify the owner, objective, and active-state filters and the final returned row. Existing tests also cover unknown-user empty result and latest-check-in filtering.
- `experiments.for_retro_window`: existing tests cover foreign key-result exclusion and the admin positive control.

`test_dual_mode_parity.py` now compares TCP and HTTPS restricted payloads for all six kinds. The HTTPS side uses the actual Supabase read dispatcher with mocked REST rows; the `krs.by_cycle`, check-in, and experiment tests assert their owner/state filters while comparing the payload to the TCP contract. Separate service-level tests retain negative cases for foreign rows and query fallback behavior.

## Verification

- RED evidence: before the TCP implementation, the injected relationship-failure test failed because `_filter_tasks_for_scope` swallowed the exception and returned no HTTP error. Before the HTTPS implementation, the owner/assignee query regressions returned only parent-goal-owned candidates and could not include the foreign-goal assignee. The real-serializer task parity regression also showed the HTTPS task was missing the nested context required by AtlasShell. The fallback title-column regression failed with `id,owner_id` before the query selected goal/objective titles. A repeat parent-visibility failure test first exposed a raw relation exception and now verifies the fixed sanitized HTTP 500.
- `.venv\Scripts\pytest.exe -q tests/test_dual_mode_parity.py tests/test_supabase_api_mode_read.py --tb=short`: **69 passed**, 2 environment warnings (Starlette/httpx deprecation and pytest cache write denial).
- `.venv\Scripts\ruff.exe check backend_app/response_scope_helpers.py backend_app/read_query_helpers.py src/services/supabase_api_mode_read.py tests/test_dual_mode_parity.py tests/test_supabase_api_mode_read.py`: **PASS**.
- `.venv\Scripts\ruff.exe format --check backend_app/response_scope_helpers.py backend_app/read_query_helpers.py src/services/supabase_api_mode_read.py tests/test_dual_mode_parity.py tests/test_supabase_api_mode_read.py`: **PASS**.
- Scoped mypy command over the four owned code/test files: **PASS**, no issues.
- Independent review `/root/t02_rereview`: **PASS** on minimal assignee-only context, TCP/HTTPS parity, fallback titles, sanitized explicit PostgREST failure, and check-in exclusions. Non-blocking test-hardening suggestion: payload assertions could reject redundant IDs/ORM columns; current serializers were independently inspected and emit the required minimal shape.
- Fresh repository-wide mypy command (`--no-incremental --ignore-missing-imports --follow-imports=skip backend_app src scripts tests`): **2 errors remain across 380 checked files**, both in unowned `backend_app/read_query_helpers.py` (line 194 arg-type and line 553 arg-type). The prior third T02-reserved error in `src/services/supabase_api_mode_read.py` is resolved.

No alignment-context API, `node.get` serializer, shared ledger, generated artifact, workflow, or T32 budget-harness files were changed.
