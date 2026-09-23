Documentation HQ: [README](../../../README.md)

# T17 Non-Authentication Status Follow-up — Snapshot

## Before

- Any non-2xx `/v1/auth/me` response threw an untyped error containing “validation failed”.
- `/session/me` treated that string as explicit revocation, returned 401, and cleared both cookies even for 429/5xx responses.

## After

- Backend status is carried by `BackendSessionValidationError`.
- Only explicit 401/403 responses clear the session and return `SESSION_REVOKED`.
- 429/5xx and network errors return fail-closed `503 BACKEND_UNAVAILABLE` while preserving the session cookies.
- Tests cover 429, 503, network outage, and explicit 401 revocation.

## Changed files

- `spa-bff/src/server.ts`
- `spa-bff/test/independent_failure_isolation.test.ts`
- `task-T17-non-auth-status-followup-brief.md`
- `task-T17-non-auth-status-followup-report.md`
