# BFF Runtime Release Gate

## Scope

This is the final runtime gate for the browser -> BFF -> backend topology. It supplements the repo evidence and the topology review, and should be used before any release or promotion that depends on the BFF trust boundary.

## Release gate

The release is allowed to proceed only if all of the following checks pass in staging or a representative pre-prod environment.

### 1. Accepted session flow
- Valid login completes successfully.
- Session cookie is issued and returned to the browser.
- A proxied route succeeds when the session matches the actor and the request is valid.
- The backend sees the expected actor identity.

### 2. Forged actor rejection
- Submit a request with a mismatched `X-OKR-Actor` value.
- Confirm the BFF rejects the request before proxying.
- Confirm the backend never receives the request.
- Record the HTTP status and response body.

### 3. CSRF enforcement
- Submit a state-changing request without a valid CSRF token.
- Confirm the request is rejected before it reaches the backend.
- Retry with the valid CSRF token and confirm success.

### 4. Allowlist enforcement
- Attempt a route that is not in the BFF allowlist.
- Confirm the error is returned by the BFF.
- Confirm no upstream backend call is attempted.

### 5. Signed request validation
- Use a valid signed BFF-to-backend request and confirm success.
- Tamper with the signature, timestamp, or nonce.
- Confirm the backend rejects the modified request.

### 6. Dependency outage handling
- Simulate or trigger a backend dependency outage.
- Confirm the BFF returns a bounded dependency-failure response.
- Confirm stale authenticated UI state is not served.

### 7. Rollback rehearsal
- Execute the documented rollback path.
- Confirm restoration duration remains within the approved window.
- Confirm last-known-good release is restored and data integrity remains verified.

## Evidence record

Capture the result of each check in the release log, including:

- timestamp
- environment name
- user/actor involved
- HTTP status
- observed response text or command output
- any screenshots, logs, or traces
- result: pass/fail
- owner and approver

## Approval criteria

Signoff requires:

- zero failed checks
- no bypass of actor binding, CSRF, or request signing
- no stale data served under dependency failure
- rollback time within the stated policy limit
- repo evidence and topology review remain green

## Current status

The repository evidence gate is already satisfied. Fresh validation command output confirms:

- Security parity evidence complete
- Failure isolation evidence complete
- Rollback evidence complete
- Topology review complete

This is the final operational slice before release signoff.
