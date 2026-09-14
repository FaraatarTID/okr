# BFF Release Runbook

Documentation HQ: [README](../README.md)

## Purpose
This runbook closes the gap between the repository evidence gate and the live staging signoff. It combines the runtime smoke checks with the release signoff criteria so a release owner can execute, record, and approve the BFF topology safely.

## Pre-flight
- Confirm the target environment is staging or pre-prod.
- Confirm the current artifact set is deployed.
- Confirm a valid user session and target actor exist.
- Confirm CSRF tokens and signed requests are enabled in the environment.
- Confirm rollback instructions are available for the current release.

## Test matrix

### 1. Happy-path request
- Action: Sign in and make a valid proxied request.
- Expected result: HTTP success, session cookie present, backend sees the matching actor.
- Evidence: response payload, session cookie, backend log snippet.
- Status: PASS / FAIL

### 2. Mismatched actor rejection
- Action: Authenticate normally, then send a request with a mismatched `X-OKR-Actor`.
- Expected result: request rejected by the BFF before proxying; backend is not called.
- Evidence: HTTP status, response body, network log or backend log.
- Status: PASS / FAIL

### 3. CSRF enforcement
- Action: Submit a change without a valid CSRF token.
- Expected result: request rejected before backend call.
- Evidence: HTTP status and error response.
- Status: PASS / FAIL

### 4. Allowlist enforcement
- Action: Access a non-allowlisted route or path.
- Expected result: 403/blocked response from the BFF.
- Evidence: response output and route log.
- Status: PASS / FAIL

### 5. Signed request validation
- Action: Tamper with a BFF-to-backend signature, timestamp, or nonce.
- Expected result: signed request is rejected by the backend.
- Evidence: request trace and backend validation output.
- Status: PASS / FAIL

### 6. Dependency outage handling
- Action: briefly force backend dependency failure.
- Expected result: bounded dependency-failure response, no stale or privileged data served.
- Evidence: BFF response, dependency log or health output.
- Status: PASS / FAIL

### 7. Rollback rehearsal
- Action: execute the documented rollback plan.
- Expected result: last-known-good release restored within the policy window and data remains verified.
- Evidence: rollback command log and integrity check output.
- Status: PASS / FAIL

## Release criteria
Proceed to promote only if:
- all runtime checks are PASS
- no forged or mismatched actor request is accepted
- no CSRF or allowlist bypass is observed
- dependency failure remains isolated
- rollback time stays within the approved limit
- repo evidence is green

## Required artifacts
- [docs/topology-review.json](../docs/topology-review.json)
- [docs/evidence/security-parity.json](../docs/evidence/security-parity.json)
- [docs/evidence/failure-isolation.json](../docs/evidence/failure-isolation.json)
- [docs/evidence/rollback-rehearsal.json](../docs/evidence/rollback-rehearsal.json)
- [docs/BFF_RUNTIME_RELEASE_GATE.md](../docs/BFF_RUNTIME_RELEASE_GATE.md)
- [docs/BFF_RELEASE_SIGNOFF_TEMPLATE.md](../docs/BFF_RELEASE_SIGNOFF_TEMPLATE.md)

## Signoff
Record the result in the signoff template and obtain release approval before any production promotion.
