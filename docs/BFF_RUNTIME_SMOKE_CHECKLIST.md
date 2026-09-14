# BFF Runtime Smoke Checklist

This checklist captures the next operational slice after the repository-level evidence and topology review gates have passed.

## Purpose

Validate the browser -> BFF -> backend trust boundary in a staging environment before promotion or release signoff. This is focused on live runtime proof, not just static repo validation.

## Preconditions

- Staging environment is deployed with the current BFF and backend build.
- Session cookies, CSRF tokens, and signed BFF-to-backend headers are enabled.
- Access to the staging browser and/or API client is available.
- A known user account is available for actor-scoped routes.

## Required checks

### 1. Happy path session flow
- Log in through the browser UI or equivalent BFF session endpoint.
- Confirm a session cookie is issued for the authenticated user.
- Confirm the UI can call a proxied backend endpoint successfully.
- Confirm the backend sees the expected actor and request metadata.

### 2. Actor mismatch rejection
- Use a valid authenticated session.
- Forge a mismatched `X-OKR-Actor` value in the BFF request flow.
- Confirm the request is rejected with a fail-closed response.
- Confirm no upstream backend call is made for that request.

### 3. CSRF enforcement
- Trigger a state-changing request without a valid CSRF token.
- Verify the request is rejected before backend mediation.
- Retry with a valid CSRF token and confirm success.

### 4. Route allowlisting
- Attempt to access a route or backend path not on the BFF allowlist.
- Confirm the BFF returns a forbidden or rejected response.
- Verify the request does not reach the backend.

### 5. Request signing validation
- Use the existing signed BFF-to-backend path and verify it succeeds.
- Tamper with a signing header or timestamp.
- Confirm the backend rejects the request.

### 6. Dependency failure handling
- Simulate backend outage or dependency failure.
- Confirm the BFF returns a bounded dependency-failure response.
- Confirm stale or privileged data is not served.

### 7. Rollback rehearsal
- Trigger the documented rollback process for the current candidate release.
- Record the restoration duration.
- Confirm last-known-good release is restored without data loss or integrity issues.

## Gate to proceed

Proceed to release signoff only when all of the following are true:

- All checks pass in staging.
- No mismatched actor header or forged request is accepted.
- Backend dependency failures are isolated and surfaced cleanly.
- The recorded restoration duration remains within the approved window.
- The runtime observations match the artifacts in the review package.

## Evidence to attach

Record the results in the release bundle, including:

- Browser/session screenshots or logs
- Request/response examples showing rejection paths
- Backend validation logs where available
- Rollback operation record and duration
- Final decision entry in the topology review metadata

## Current repo status

The repository-level evidence gate is already passing. Fresh validation output confirms:

- `uv run python -m scripts.validate_security_parity docs/evidence/security-parity.json`
- `uv run python -m scripts.validate_failure_isolation docs/evidence/failure-isolation.json`
- `uv run python -m scripts.validate_rollback_rehearsal docs/evidence/rollback-rehearsal.json`
- `uv run python -m scripts.validate_topology_review docs/topology-review.json`

All completed successfully with exit code 0.
