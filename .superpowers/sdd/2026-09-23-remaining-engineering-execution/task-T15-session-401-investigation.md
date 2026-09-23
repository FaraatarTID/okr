# T15 session 401 investigation

## Question

The full Playwright role-route run reportedly received `/session/me` 401 responses about 29 seconds after admin login, despite the fixture setting `BFF_SESSION_TTL_SECONDS=28800`. The failure was described as the `/timeline` route returning to login.

## First investigation (pytest-7649)

- The T15 fixture explicitly overrides the BFF environment with `BFF_SESSION_TTL_SECONDS="28800"` in `tests/test_e2e_playwright_spa_login_to_atlas.py`.
- `spa-bff/src/config.ts` reads that setting into `config.sessionTtlSeconds`; `spa-bff/src/server.ts` supplies it to `issueSessionToken` and both session-cookie issuers after successful login.
- `spa-bff/src/session.ts` sets the signed token expiry and cookie `Max-Age` from the configured TTL (with only a 60-second minimum). The implementation does not explain expiry at 29 seconds if the fixture value reached the running BFF.
- `/session/me` first calls `readSessionUserFromRequest`. A failed local cookie/token check returns 401 immediately and does not call the backend. Backend validation failures instead log `bff_session_validation_failed`; an explicit backend rejection clears both cookies and responds as `SESSION_REVOKED`.
The original failing-run directory `pytest-7649/playwright_spa_e2e0` was no longer present. Its 401s could not be attributed from that run alone.

## Focused reproduction

Only the failing role-route test was rerun, with temporary test-only diagnostics for role, final URL/body, `/api/session/me` response status/code, and cookie metadata. Cookie values were never logged. Temporary diagnostics were removed after the run.

Command:

```powershell
$env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -s -q tests/test_e2e_playwright_spa_login_to_atlas.py::test_role_route_surfaces_and_admin_access
```

The run used elevated process context for fixture child cleanup. It failed after **156.50s** on the member's `/timeline` route. Admin and manager completed their requested routes with session cookies present and `/api/session/me` returning 200. Member login also succeeded; its session cookie remained present with an expiry roughly eight hours ahead until `/timeline`.

The member route then produced `/api/session/me` 401 `SESSION_REVOKED`, followed by 401 `MISSING_SESSION` after the BFF cleared the cookies. BFF log `pytest-7658/playwright_spa_e2e0/bff.log` records `bff_session_validation_failed` at `2026-09-23T13:20:49.980Z`, code `SESSION_REVOKED`, and again at `.025Z`. The BFF log also records a proxied read-query 429 at `13:20:48.647Z`.

The matching backend log records, for actor `e2e_member`:

- `POST /v1/read/query` 429 at `13:20:48.644590Z`;
- `GET /v1/auth/me` 429 at `13:20:49.978150Z`;
- another `GET /v1/auth/me` 429 at `13:20:50.018907Z`.

This is a **backend per-client-IP rate limit**, not expiry. `backend_app/config.py` defaults to 120 requests per 60 seconds, and `backend_app/security.py` keys the authenticated BFF requests by trusted client IP. The E2E services share loopback IP, so the role-route test's repeated UI/read/session requests consume one bucket across all roles. The run artifact is `.test-artifacts/pytest-subproc/pytest-of-Mirshekari/pytest-7658/playwright_spa_e2e0/`.

There is a second, session-authority behavior implicated: `spa-bff/src/server.ts:225` converts every non-2xx `/v1/auth/me` response into the same `Backend session validation failed: <status>` error, and `server.ts:454` classifies that phrase as an explicit auth rejection. Consequently, a backend 429 is reported as `SESSION_REVOKED` and clears the browser cookies. The test demonstrates the immediate trigger (aggregate test traffic reaches 429) and the BFF's misclassification/clearing behavior. It does not demonstrate a 29-second configured cookie lifetime.

## Scope and follow-up

No auth implementation was changed, as instructed. The backend test-rate-limit setup is a T15 fixture/acceptance concern; BFF 429 classification is in T17 session authority; rate-limit behavior belongs to its security packet. Coordinator should route these two findings to their owners before considering any fix. Do not change session TTL to address this failure.

Post-run cleanup check found no listening process on the fixture's three ports (backend `50608`, BFF `50609`, SPA `50610`), confirming the test-owned services exited. Pytest later pruned the original full logs, so the relevant sanitized excerpts were preserved in `t15-session-401-repro-7658/`.

The E2E fixture sets `OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS=10000`, with an inline comment that T15 does not test rate limiting and all simulated users share the trusted loopback IP.

## Focused rerun after BFF 429 fix

After the BFF 429 handling fix passed its BFF suite, the role-route case was rerun with the test-only rate limit override. Temporary browser diagnostics recorded role, URL, `/api/session/me` status/code, and session-cookie metadata without cookie values. Diagnostics were removed after the run.

Command:

```powershell
$env:OKR_RUN_PLAYWRIGHT_SPA_E2E='1'
.venv\Scripts\python.exe -m pytest --basetemp=.test-artifacts/t15-role-route-rerun-20260923 -p no:cacheprovider -s -q tests/test_e2e_playwright_spa_login_to_atlas.py::test_role_route_surfaces_and_admin_access
```

Result: **1 passed in 42.65s**. Admin, manager, and member all completed `/dashboard`, `/daily`, `/timeline`, and `/retrobox` with their session cookies present and `/api/session/me` returning 200. The initial 401 `MISSING_SESSION` responses occurred on each fresh role context before login. No `SESSION_REVOKED`, backend 429, or route redirect appeared in the captured logs. The persistent run logs are under `.test-artifacts/t15-role-route-rerun-20260923/playwright_spa_e2e0/`.

Cleanup verification found no listeners on the three fixture service ports. `rg T15_SESSION_DIAG tests/test_e2e_playwright_spa_login_to_atlas.py` found no output after removing the temporary instrumentation.
