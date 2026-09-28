# T23 — Per-session shared revocation design

Documentation HQ: [README](../../../README.md)

Status: **Owner approved the written specification on 2026-09-27; admin deprovisioning is retained in D3 after T19 confirms the stable user identity mapping.**
Decision record: [T22 D3 decision](../../../.superpowers/sdd/2026-09-23-remaining-engineering-execution/task-T22-decision.md)
Authoritative issue: [D3 in the remaining engineering plan](../../REMAINING_ENGINEERING_PLAN.md#workstream-d---spa-bff-and-identity)
Execution packet: [T23](../plans/2026-09-23-remaining-engineering-execution.md)

## Goal

Replace the SPA BFF's process-local, fail-open session registry with backend-owned
shared state. A session issued by one BFF instance must be recognized by every
instance, logout must revoke only that session across instances and restarts, an
unknown session must not authenticate, and inability to read or write the shared
state must deny the protected operation.

This is per-session revocation. T21's account-wide `token_version` check remains
independent and can revoke all sessions for an account when an authorized version
bump occurs. It does not replace this design.

## Approved architecture

1. **Backend owns state and policy.** The backend exposes a narrow session-registry
   port backed by its configured shared durable security-state provider. The BFF
   has no database or Redis client and cannot choose a storage implementation.
2. **Signed service boundary.** BFF registration, revocation, and session-bearing
   protected requests use the existing service token and request-signing boundary.
   The session identifier and session actor must be covered by the authenticated
   request contract; adding an unsigned header that can be altered independently
   of the request signature is not sufficient. The backend verifies service
   credentials/signature before acting on registry data.
3. **Register before issuing.** After successful authentication, the BFF creates a
   fresh random session identifier and expiry, asks the backend to register it,
   and only then returns the signed session cookie. A registration failure returns
   503 and issues no session cookie. The session ID remains an opaque random
   credential component; persisted lookup uses a one-way digest of it.
4. **Check on every authenticated operation.** Each actor-authenticated request
   proxied by the BFF carries the session identifier and actor binding under the
   signed service contract. The backend's common authenticated-request path checks
   the registry before route work. `/session/me` performs the same check through
   its signed backend call. A local cookie signature/expiry check is necessary but
   never sufficient. The check is in the backend request path so it applies across
   BFF instances and cannot be skipped by a BFF route handler.
5. **Revoke before reporting logout success.** Logout submits the presented
   session identifier to the backend. On successful revocation, the BFF clears
   session and CSRF cookies and reports success. Revocation is idempotent for an
   already-revoked or unknown identifier. If the backend cannot establish that
   revocation was recorded, logout returns 503 and does not report success; the
   client retains the cookie so it can retry. The next protected request remains
   subject to the backend registry check.
6. **No fallback to process memory.** Production behavior must fail closed if the
   durable provider is missing, unavailable, or not shared. A process-local store
   may be used only by isolated tests and explicitly non-production development.

## Registry contract

The storage port needs explicit operations rather than `get_app_state()`'s
`None`-on-missing shape:

- `register(session_id_digest, actor_id, expires_at)` atomically creates an active
  record. Reuse of the same digest with a different actor or expiry is rejected;
  a random collision is not silently treated as a new session.
- `check(session_id_digest, actor_id, now)` returns exactly `active`, `revoked`,
  `unknown`, or `unavailable`. A present record must match the actor and remain
  within its credential lifetime. A missing row is `unknown`, never active.
- `revoke(session_id_digest, now)` atomically changes active state to revoked;
  repeating it is safe. Unknown is already non-authenticating. Revocation is
  retained through the signed credential's last acceptable second.
- Storage, connectivity, schema, or decoding errors produce `unavailable`; they
  must not be collapsed to `unknown`, `active`, or an empty registry.

Persist only what registry behavior needs: the session ID digest, stable internal
actor ID, expiry, revocation state/time, and creation metadata needed for cleanup
or audit. Do not persist cookie contents, signing secrets, access tokens, or email
as an identity key. `external_subject` linking and subject-wide revocation remain
gated on T19's verified identity contract; email is not a substitute. Keep expired
records through `exp == now` because the current BFF credential accepts that
boundary; cleanup is safe only once `expires_at < now`.

The store must support concurrent BFF/backend workers and restarts. Database
uniqueness/transactions or equivalent atomic provider operations must prevent
duplicate-registration and revoke/check races from creating an active unknown
record. Reusing `backend_distributed_state` is acceptable only if it provides the
same explicit, atomic semantics without breaking existing generic-state callers;
otherwise add dedicated typed tables/keys through the backend security-state
provider. Do not use the current `get_app_state()` interface where its error and
missing-value behavior cannot distinguish unavailable from unknown.

## Request and response behavior

| Situation | Backend result | BFF/browser behavior |
| --- | --- | --- |
| Registered, unexpired session; actor matches | `active` | Continue operation. |
| Missing registry entry, actor mismatch, expired credential, or revoked entry | Authentication rejection (`401`) | Do not proxy route work; clear cookies for `/session/me` or the next browser response that establishes rejection. |
| Registry/provider unavailable or inconsistent | `503` | Do not proxy route work; preserve cookies for retry and report temporary verification failure. |
| Login registration fails | `503` | Return no session cookie; no usable signed credential is issued. |
| Logout revocation succeeds, including already unknown/revoked | success | Clear session and CSRF cookies. |
| Logout cannot confirm durable revocation | `503` | Do not claim logout success; preserve cookies for retry. |

An operation already admitted before a concurrent revocation may finish. Every
subsequent backend request must observe the revoked record. The implementation
must state this request-boundary guarantee and must not imply cancellation of
in-flight work.

## Legacy-session cutover

The new checker rejects every session ID absent from the registry. Existing
process-local records cannot be imported safely: they are incomplete across
instances/restarts, and sessions in other workers would remain unrepresented.
Deploy the backend capability and BFF registration/check/revoke flow as one
coordinated cutover. At cutover, preexisting cookies are treated as unknown and
must reauthenticate. Do not add a temporary unknown-ID allow rule, opportunistic
auto-registration on first request, or migration from process memory. Document
the expected one-time sign-in impact in the release notes/runbook.

## Authorization and scope boundaries

- Browser logout is per-session and does not require identity-wide lookup.
- Administrative deprovisioning is retained as part of D3, as required by the
  canonical register. It must require the existing administrator authorization
  and CSRF protections, resolve the provisioned target to its stable backend
  user ID under the T19 identity-link contract, and revoke all of that user's
  registered sessions. It cannot accept a caller-selected actor without
  checking authority. Add the route only after T19 confirms this identity
  mapping, then include it in the OpenAPI, generated client, route-policy,
  allowlist, and mutation-auth-matrix chain.
- Do not add a SCIM/service-to-service deprovision route until T25 records the
  concrete customer requirement and owner. When authorized, it must use a distinct
  authenticated service contract and must not weaken browser admin controls.
- Do not infer or backfill `external_subject` from usernames, email addresses, or
  unverified login responses. Resolve the T19 target identity invariant and
  provisioning authorization before identity-wide revocation is enabled.
- D4's Origin and CSRF checks remain in force for browser logout and authenticated
  writes. The registry is not a CSRF defense or a replacement for route policy.

## Implementation seams

The implementation packet should reserve and integrate these surfaces serially:

- `spa-bff/src/session.ts`: token structure and async session verification; remove
  the process-local authority, unknown-ID allow behavior, and synchronous-only
  authentication assumption.
- `spa-bff/src/server.ts`: register before login cookie issuance; check session on
  `/session/me` and every actor-required proxied operation; call durable revoke on
  logout; map explicit reject and unavailable outcomes without turning outages
  into authentication success.
- `spa-bff/src/signing.ts` and `backend_app/security.py`: bind the session/actor
  assertion to the signed request contract and verify it centrally.
- `backend_app/security_state.py` plus a focused backend router/service: provide
  typed atomic registry operations and authenticated internal endpoints or
  dependencies. Keep these endpoints unavailable to direct browser callers.
- `backend_app/main.py`, request/response schemas, exported OpenAPI, generated
  BFF schema/client, `spa-bff/src/allowlist.ts`, route-policy and mutation-auth
  matrix: update together if a public-facing or generated route contract changes.
- Login/session, signing, protected-route, logout, backend provider, route-policy,
  and integration tests: reserve files before parallel implementation; shared
  files are integrated by one steward at a time.

Prefer central backend enforcement on each signed actor-bound request over a
separate BFF-only preflight call: the latter leaves each protected route dependent
on every BFF handler remembering a check and introduces a check/proxy gap. If
implementation constraints require a separate check endpoint, the reviewer must
show that all actor-required routes are covered and document the in-flight/race
semantics before accepting the deviation.

## Acceptance tests and operational evidence

T23 is not complete until all of these pass:

1. **Registration ordering:** successful login registers the session before any
   cookie is emitted; backend registration failure yields 503 and no session or
   CSRF cookie usable as an authenticated session.
2. **Per-session semantics:** two sessions for one actor are registered; revoking
   one makes that session fail while the other remains active.
3. **Unknown and tampered IDs:** fabricated, malformed, actor-mismatched, and
   unknown session IDs reject. Removing/altering the signed session assertion
   cannot turn a protected request into an accepted one.
4. **Cross-instance and restart behavior:** register on instance A, authenticate
   on B, revoke on A, and reject on B; restart the BFF/backend process and confirm
   the revoked result remains. Exercise the configured shared provider, not two
   clients backed by one in-memory object.
5. **Failure behavior:** inject unavailable storage for register/check/revoke;
   protected work does not run, each request returns 503, and no branch falls back
   to active. Login emits no session cookie. Logout does not claim success when
   revocation cannot be confirmed.
6. **Expiry boundary and cleanup:** accept/check the session at `exp == now`,
   reject after expiry, and prove cleanup cannot erase the record while the signed
   credential is still accepted.
7. **Logout behavior:** real BFF logout revokes durable state before clearing
   cookies; replay on another BFF instance is rejected. Unknown/repeated logout
   remains safe and clears the presented cookie.
8. **Protected operation matrix:** every actor-required BFF allowlisted operation
   reaches backend session enforcement; include read POSTs, mutation methods,
   `/session/me`, and a route intentionally not allowlisted to confirm it is still
   rejected by BFF policy.
9. **Authorization boundaries:** any shipped admin deprovision path rejects
   non-admin, missing/invalid CSRF, and caller-selected unrelated actors; SCIM
   behavior is omitted unless T25 has been resolved.
10. **Contract generation:** backend OpenAPI drift, BFF schema/allowlist, route
    policy, signed-request contract, and mutation-auth matrix checks pass as one
    integrated set.

Also run the T23 cross-instance/store-outage drill against the configured shared
provider and retain evidence of provider type, instance identities, restart,
expiry boundary, request IDs, and outcomes. A local unit test or two BFF objects
sharing a process-local map does not satisfy this drill. Do not claim deployment
verification unless the actual shared production-like topology was exercised.

## Non-goals and gates

- No OIDC routes or login exposure; D2/D4 remain the coupled T24 unit.
- No assumption that T20's token verifier, T19 identity link, or provider facts
  have changed their open/gated status.
- No automatic account-wide `token_version` bump on logout; logout is per-session.
- No session persistence in the BFF, SPA, or a BFF-owned database/Redis client.
- No SCIM feature before T25 and no identity backfill before T19 authorization.
- No claim that local acceptance tests close production D3 without the required
  shared-store drill and canonical register update.

## Self-review before owner review

- The design preserves T22's explicit per-session choice and does not silently
  substitute T21's account-wide invalidation.
- Unknown IDs and unavailable state have separate outcomes; neither can fall
  through to active.
- The login order prevents a cookie from escaping before shared registration.
- The backend checks on each authenticated request, so a BFF route cannot omit
  an independent preflight and the store result is not trusted from the browser.
- The signed session/actor binding is called out because the existing request
  signature does not automatically authenticate arbitrary new headers.
- The old registry cannot be migrated safely across workers; deliberate
  reauthentication avoids trusting a partial import.
- T19, T20, T24, and T25 boundaries remain explicit. Subject-wide identity data,
  OIDC exposure, and SCIM are not smuggled into this packet.
- The owner approved this detailed spec on 2026-09-27. Following the canonical
  D3 requirement, administrative deprovisioning is retained, but route
  integration waits for T19's stable user identity mapping and generated API
  contract.
