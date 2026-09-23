Documentation HQ: [README](../../../README.md)

# T03 review snapshot

Base: current shared checkout, without Git writes. The implementation consists only of the two new test files and `task-T03-report.md`; all production, contract, generated, and shared-ledger files stayed untouched by T03.

| File | Review focus |
| --- | --- |
| `tests/test_read_actor_presence.py` | Seven parameterized backend HTTP cases each for missing actor, forged payload actor, and authorized real SQLite reads; single `node.get` serializer seam follows real `get_node`. |
| `spa-bff/test/read_actor_presence.test.ts` | Seven parameterized missing-session cases with no fetch and seven valid-session actor-forwarding cases. |
| `task-T03-report.md` | Seven-row route/downstream matrix, command results, and separate detached serializer defect. |

Source baseline for comparison: `spa-bff/src/server.ts`, `spa-bff/src/proxy.ts`, `spa-bff/src/route-policy.json`, `backend_app/routers/platform_routes.py`, `backend_app/security.py`, `backend_app/read_query_helpers.py`, `src/crud_query_helpers.py`, `src/crud_experiment_helpers.py`. The tests execute these sources; no source-string-only assertion stands in for a request-path refusal.
