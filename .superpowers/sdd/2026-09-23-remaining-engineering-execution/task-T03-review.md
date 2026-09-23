Documentation HQ: [README](../../../README.md)

# T03 independent review

Verdict: **PASS** for the actor-presence audit. No blocking T03 findings. Deferred minors: none.

Reviewed the brief, report, snapshot, both new test files, and the real BFF/backend/CRUD paths against the checkout. The inspected production and contract files have no Git diff. T03 changes consist of tests and its records; no task-visibility predicate or T02 product decision was introduced.

## Evidence

- All seven named F2 kinds appear in both parameter matrices. Each BFF missing-session case uses a forged payload actor, receives `MISSING_SESSION` 401, and asserts no backend fetch. Each positive BFF case creates a real signed session and checks exactly one fetch, the verified actor header, and the original kind/params.
- Each backend absence/mismatch case calls the actual `/v1/read/query` route with existing seeded identifiers and confirms 400/403 before the real scope resolver is entered. Source inspection confirms actor resolution precedes `_read_query_payload` and every protected read. These route-level refusals are upstream of either database-mode dispatch.
- Positive backend cases use the real SQLite store, actor scope resolver and downstream scoped readers. The five `get_node` branches operate on existing objects, so dropping the actor triggers the existing `UnscopedNodeReadError` rather than passing through a missing-row path. The two experiment branches call their real `_authorize_node_scoped_access` and return a seeded running experiment. Work-log/alignment result collections may be empty, but their protected parent lookups are real and occur before those collections are built; this does not produce a reject-all positive control.
- The `node.get` serializer seam is installed only in its positive case. `read_query_helpers.py` calls real `get_node(..., actor_username=actor)` before that seam. The seam requires a real Task with the seeded ID and supplies the matching owner for the later scope guard. It cannot bypass actor absence in the refusal tests, and does not replace the real node authorization.
- The report explicitly discloses that unpatched Goal/Task `node.get` serialization encountered `DetachedInstanceError` and that the full response is not proven by T03. The source is consistent with that explanation: scoped Task loading does not eagerly load the parent chain which its full serializer traverses. Preserve this separate defect in T02 or an explicit scoped follow-up before claiming complete Goal/Task payload correctness; this review does not close it. I did not independently reproduce the full unpatched error trace.

## Independent verification

- `.venv\Scripts\pytest.exe -q tests/test_read_actor_presence.py tests/test_crud_authorization.py -p no:cacheprovider`: **36 passed**, one existing Starlette/httpx deprecation warning.
- `npm run test --workspace spa-bff -- read_actor_presence.test.ts allowlist.test.ts`: **23 passed**, two files.
- `git diff --exit-code` for the inspected BFF policy/proxy/server, backend route/security/read/serialization, and CRUD authorization files: exit 0.

This approval covers composed BFF/backend actor boundaries and the scoped downstream database path. It is not deployed browser/IdP evidence or an HTTPS payload-parity claim.
