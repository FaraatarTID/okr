# BFF Release Signoff Template

Documentation HQ: [README](../README.md)

## Release metadata
- Release ID:
- Environment:
- Date:
- Operator:
- Approver:

## Topology decision
- Decision: retain_bff / simplify_topology
- Review artifact: [docs/topology-review.json](../docs/topology-review.json)

## Repository evidence status
- Security parity: PASS / FAIL
- Failure isolation: PASS / FAIL
- Rollback rehearsal: PASS / FAIL
- Topology review: PASS / FAIL

## Runtime smoke checks

### 1. Accepted session flow
- Result: PASS / FAIL
- Evidence: attach session cookie, response output, trace or screenshot
- Notes:

### 2. Forged actor rejection
- Result: PASS / FAIL
- Evidence: attach request/response and backend logs
- Notes:

### 3. CSRF enforcement
- Result: PASS / FAIL
- Evidence: attach request/response and security logs
- Notes:

### 4. Allowlist enforcement
- Result: PASS / FAIL
- Evidence: attach blocked route output
- Notes:

### 5. Signed request validation
- Result: PASS / FAIL
- Evidence: attach valid and tampered request examples
- Notes:

### 6. Dependency outage handling
- Result: PASS / FAIL
- Evidence: attach BFF failure response and logs
- Notes:

### 7. Rollback rehearsal
- Result: PASS / FAIL
- Evidence: attach rollback duration and integrity record
- Notes:

## Exit criteria
- [ ] All runtime smoke checks passed
- [ ] No actor mismatch accepted
- [ ] No CSRF bypass accepted
- [ ] No allowlisted route bypass accepted
- [ ] No stale data served during dependency failure
- [ ] Rollback remains within the approved window
- [ ] Repo evidence and topology review stayed green

## Final approval
- Release approved: YES / NO
- Approval signature:
- Approval timestamp:
