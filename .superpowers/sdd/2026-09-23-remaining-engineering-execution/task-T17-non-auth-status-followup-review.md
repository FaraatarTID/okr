Documentation HQ: [README](../../../README.md)

# T17 Non-auth Status Follow-up Independent Review

## Verdict: PASS

The source change correctly narrows cookie clearing to `BackendSessionValidationError` carrying backend status 401 or 403. A 429/5xx response becomes the `BACKEND_UNAVAILABLE` 503 envelope; transport exceptions also fail closed through the generic catch path. Neither transient path sets clearing cookies.

Coverage distinguishes the required outcomes:

- The network-failure case now asserts status 503, `BACKEND_UNAVAILABLE`, and no `Set-Cookie`.
- Parameterized backend 429 and 503 cases assert the same fail-closed response and no `Set-Cookie`.
- The explicit backend 401 control asserts 401, `SESSION_REVOKED`, and a clearing cookie (`Max-Age=0`).

The follow-up diff adds only the missing cookie-preservation assertion to the network-failure case. No blocking findings remain.

## Verification

`npm test -- --run test/independent_failure_isolation.test.ts` in `spa-bff` — **4 passed**.
