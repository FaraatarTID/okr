# BFF Security Boundary Review

Documentation HQ: [README](../README.md)

Status: `IMPLEMENTED WITH RESIDUAL REVIEW` for P0-03.

This is a repository-grounded control review for the pre-SaaS BFF boundary. It
is not a penetration test or an independent security audit.

## Observed controls

| Control | Owner | Evidence | Assessment |
|---|---|---|---|
| Signed BFF-to-backend requests | `spa-bff` and backend API | `buildBackendSecurityHeaders` used for proxy and session validation calls | Backend can reject unsigned or tampered edge requests |
| Session token integrity and expiry | `spa-bff` | `issueSessionToken` and `readSessionUserFromCookie` use configured secret and TTL | Cookie contents are not trusted without verification |
| Browser cookie protection | `spa-bff` | Session cookie is HttpOnly; cookies use SameSite policy and configurable Secure flag | Browser scripts cannot read the session cookie |
| CSRF protection | `spa-bff` | Double-submit token required for state-changing actor-scoped requests | Read-only POST routes are explicitly excluded from CSRF requirement |
| Actor binding | `spa-bff` and backend API | Session actor replaces mismatched attempted actor; backend receives signed actor headers and rejects mismatched forwarded `X-OKR-Role` / `X-OKR-Roles` claims | Client cannot select a different actor or role through a conflicting header |
| Session revocation handling | `spa-bff` | `/session/me` clears cookies and returns 401 on backend validation rejection | Revoked sessions fail closed |
| Backend outage handling | `spa-bff` | `/session/me` returns bounded 503 and does not serve stale authenticated data | Availability failure is distinct from authorization success |
| Route exposure | `spa-bff` | Generated allowlist, actor-required metadata, and OpenAPI operation-ID mapping | Unlisted or undocumented browser paths are rejected before proxying |
| Download contract preservation | `spa-bff` | Proxy preserves client `Accept`, upstream binary bytes, `Content-Type`, and `Content-Disposition` | Documented binary downloads remain usable through the BFF |

## Evidence captured

- `npm run check:allowlist` passed with 44 routes.
- `npm --prefix spa-bff test` passed with 16 test files and 233 tests (measured 2026-09-29; the count grows with every new test, so re-measure rather than trust this figure).
- OpenAPI drift, generated SPA/BFF types, BFF allowlist, SPA operation manifest, and direct-fetch boundary checks are enforced by the contract-quality CI lane. See [openapi-contract-synchronization.md](openapi-contract-synchronization.md).
- Backend mutation API and dual-mode parity coverage passed: `tests/test_backend_mutation_api.py` (120 tests) and `tests/test_dual_mode_parity.py` (61 tests), measured 2026-09-29. The earlier figure of 128 could not be reproduced from any combination of files, so it has been replaced by the measured per-file counts.
- Backend ingress security regression passed: `tests/test_backend_private_ingress_enforcement.py` (6 tests, signed requests and replay protection) and `tests/test_forwarded_role_claims_fail_closed.py` (11 tests, forwarded role-claim enforcement, which fails closed as of 2026-09-29).
- Live Compose baseline showed the BFF and backend processes running independently.

## Residual risks and required follow-up

- Production secret rotation and key-version overlap need an operational rehearsal.
- Deployment-origin settings need environment-specific review. Origin validation itself is **not implemented** in `spa-bff`: no request header is consulted to decide whether to accept a request, and no allowlisted-origin configuration exists, so this is a missing control rather than a tuning task.
- Rate limiting is **not implemented** at the browser edge, so there is no threshold to tune. Rate-limit effectiveness and abuse thresholds need measured production-like traffic evidence once a BFF limiter exists; today the only request budget in the system belongs to the backend hop, which the BFF's forwarded client IP lets the backend apply.
- Tenant-context propagation is deferred until the canonical SaaS boundary is approved.
- Removing or thinning the BFF still requires rollback and security-parity evidence.

## Decision impact

The observed controls support retaining `spa-bff` as a separate pre-SaaS browser
boundary. They do not approve permanent topology, SaaS tenant isolation, or BFF
removal.
