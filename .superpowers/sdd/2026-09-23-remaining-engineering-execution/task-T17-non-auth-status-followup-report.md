# T17 Follow-up — Transient session-validation statuses

## Result

Implemented the T15-discovered BFF status-classification fix. The BFF now clears session cookies only when `/v1/auth/me` returns an explicit 401 or 403. Backend 429/5xx responses and transport failures remain fail-closed as `503 BACKEND_UNAVAILABLE` and preserve the browser cookies.

## Test-first evidence

- Added tests for backend 429 and 503 responses with a valid BFF cookie; each must return the transient `BACKEND_UNAVAILABLE` envelope without `Set-Cookie` clearing.
- Added an explicit backend 401 control proving `SESSION_REVOKED` still returns 401 and clears cookies.
- The initial red run showed both 429 and 503 incorrectly returned 401; the explicit-control behavior itself was correct (the first assertion needed to account for Fastify's multiple `Set-Cookie` headers).
- Added `BackendSessionValidationError` carrying the backend response status; only status 401 or 403 maps to explicit auth rejection. All other failures follow the existing transient 503 branch.

## Verification

- `npm test -- --run test/independent_failure_isolation.test.ts` — 4 passed.
- `npm test --workspace spa-bff` — **120 passed**.
- `npm run typecheck --workspace spa-bff` — passed.
- `npm run build --workspace spa-bff` — passed.
- `npm exec eslint -- spa-bff/src/server.ts spa-bff/test/independent_failure_isolation.test.ts` — passed.

## Scope boundary

No route, rate-limit threshold, session-token format, OIDC, or cookie TTL changed. T15 raises only its isolated E2E fixture's rate-limit ceiling because three simulated roles share one test loopback IP; that change is recorded in the T15 report. The focused T15 role-route rerun is pending. Independent review returned **PASS** after requesting and receiving an assertion that transport failures preserve cookies; see `task-T17-non-auth-status-followup-review.md`.
