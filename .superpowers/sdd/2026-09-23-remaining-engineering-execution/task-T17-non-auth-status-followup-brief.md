Documentation HQ: [README](../../../README.md)

# T17 Follow-up — Preserve BFF cookies on transient backend status

## Trigger

The T15 opted-in role-route test reproduced a backend 429 from `GET /v1/auth/me` after its simulated admin/manager/member traffic shared loopback client IP. The BFF classified every non-2xx status as explicit session revocation, returned 401, and cleared both cookies. A still-valid member cookie had about eight hours remaining. The request itself was throttled; no invalid token version or missing user was reported.

## Contract

- Clear/revoke the browser session only when the session-validation response is an explicit authentication rejection (backend 401 or 403, subject to the existing endpoint contract).
- A transient or operational status such as 429 or 5xx must fail closed for that request while preserving the browser cookies, matching existing backend-unavailable behavior. Return the existing `503 BACKEND_UNAVAILABLE` envelope unless a more specific documented contract requires otherwise.
- Keep current response and cookie-clearing behavior for actual expired, invalid, or revoked sessions.

## Exact ownership

- `spa-bff/src/server.ts`
- `spa-bff/test/server.test.ts` or `spa-bff/test/independent_failure_isolation.test.ts`
- This follow-up brief/report/review only; coordinator owns `progress.md`.

No OIDC routes, rate-limit policy, allowlist, frontend behavior, or session-token format changes.

## Acceptance

- Add a failing test first: `/session/me` with a valid BFF cookie and backend 429 returns transient failure and does not send a clearing `Set-Cookie`.
- Add/retain a positive control proving explicit 401 revocation still returns 401 and clears cookies.
- Add/retain a 5xx/network failure check proving fail-closed and cookie preservation.
- Run focused BFF tests, typecheck, lint, and build.
