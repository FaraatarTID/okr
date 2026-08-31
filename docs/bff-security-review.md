# BFF Security Boundary Review

Back to [Documentation HQ](README.md).

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
| Actor binding | `spa-bff` and backend API | Session actor replaces mismatched attempted actor; backend receives signed actor headers | Client cannot select a different actor through a conflicting header |
| Session revocation handling | `spa-bff` | `/session/me` clears cookies and returns 401 on backend validation rejection | Revoked sessions fail closed |
| Backend outage handling | `spa-bff` | `/session/me` returns bounded 503 and does not serve stale authenticated data | Availability failure is distinct from authorization success |
| Route exposure | `spa-bff` | Generated allowlist and actor-required metadata | Unlisted browser paths are rejected before proxying |

## Evidence captured

- `npm run check:allowlist` passed with 44 routes.
- `npm test` passed with 65 BFF tests.
- Backend mutation API and dual-mode parity coverage passed with 128 tests.
- Live Compose baseline showed the BFF and backend processes running independently.

## Residual risks and required follow-up

- Production secret rotation and key-version overlap need an operational rehearsal.
- Cookie domain, Secure flag, proxy trust, and deployment-origin settings need environment-specific review.
- Rate-limit effectiveness and abuse thresholds need measured production-like traffic evidence.
- Tenant-context propagation is deferred until the canonical SaaS boundary is approved.
- Removing or thinning the BFF still requires rollback and security-parity evidence.

## Decision impact

The observed controls support retaining `spa-bff` as a separate pre-SaaS browser
boundary. They do not approve permanent topology, SaaS tenant isolation, or BFF
removal.
