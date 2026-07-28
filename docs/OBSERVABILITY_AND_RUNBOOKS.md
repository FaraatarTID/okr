# Operations Observability Stack and Incident Runbooks
Documentation HQ: [README](../README.md)

This document closes `OBS-02` by defining the production operations visibility model in a single, concrete artifact.  
It is the single source of truth for what to monitor, what to alert on, and how to respond.

Related runbook and ops docs:
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [DEPLOYMENT_OPERATIONS_GUIDE.md](DEPLOYMENT_OPERATIONS_GUIDE.md)

## Scope

- Signals covered: API health, BFF boundary health, worker/job health, DB/migration health, authentication/rate-limits, and audit integrity.
- Evidence format: each signal includes status meaning, alert policy, and response action.
- Primary runtime context: `backend-api`, `backend-worker`, `spa-bff`, `spa-web`, PostgreSQL, Redis (if enabled), and orchestrator events.

## Dashboard definitions (first-class set)

### 1) API Service Health Dashboard

- **Service:** `backend-api`
- **Key widgets:**
  - `/healthz` success rate and latency.
  - Route request volume by method and route.
  - HTTP status distribution (`2xx`, `4xx`, `5xx`) for all mutation/read routes.
  - Request IDs with correlation ratio (`request_id`/`correlation_id` present and stable across middleware/handlers).
  - Error envelope consistency ratio (errors with structured JSON envelope).
- **Owner:** Backend engineering.

### 2) BFF Boundary Dashboard

- **Service:** `spa-bff`
- **Key widgets:**
  - Proxy request pass/fail rate.
  - `/api/request` and `/auth` latency percentile charts.
  - Backend auth failures grouped by actor/header mismatch.
  - Timeout and upstream error surfacing count.
  - Health check trend and startup preflight diagnostics counts.
- **Owner:** Platform/API team.

### 3) Worker Health and Queue Dashboard

- **Service:** `backend-worker`
- **Key widgets:**
  - Job queue depth by status (`PENDING`, `RUNNING`, `DONE`, `FAILED`, `RETRY`).
  - Average job age and max in-progress duration.
  - Retry-rate and terminal-failure trend.
  - Dead-letter-like marker count for repeated retry exhaustion.
  - Poll loop lag and worker heartbeat/uptime.
- **Owner:** Platform/infra.

### 4) Data Layer and Migration Dashboard

- **Service:** PostgreSQL (or managed equivalent)
- **Key widgets:**
  - Active DB connections and connection-age histogram.
  - Migration event age and current migration version.
  - Slow query trend for critical paths (read graph endpoints, job polling, write mutations).
  - Lock wait and long-running transaction count.
- **Owner:** Platform/data team.

### 5) Auth and Security Control Dashboard

- **Service:** `backend-api` + `spa-bff`
- **Key widgets:**
  - Login failure count and unique user failure cardinality.
- **Owner:** Security.

### 6) Audit and User-impact Dashboard

- **Service:** `backend-api`
- **Key widgets:**
  - Audit events by actor, target, and endpoint.
  - Write-to-read reconciliation delay indicators.
  - Error bursts by route and actor scope.
- **Owner:** Operations/SRE.

## Alert rules

### API and BFF reliability

1. **API 5xx surge**
   - Condition: > 20 5xx responses in 5 minutes or error ratio > 5%.
   - Severity: P1.
   - Action: escalate to on-call; inspect request/error envelopes and dependency failures.

2. **BFF upstream error surge**
   - Condition: > 10 upstream backend failures to `backend-api` in 5 minutes or repeated 502/504.
   - Severity: P1.
   - Action: verify backend health, DB/network paths, and auth token propagation.

3. **Login failure spike**
   - Condition: > 25% login failures by unique actor in 10 minutes.
   - Severity: P2.
   - Action: trigger credential-risk triage and temporary lock mitigations.

### Worker and queue safety

4. **Worker no-heartbeat**
   - Condition: no successful worker heartbeat in 3 minutes while queue has non-zero runnable jobs.
   - Severity: P1.
   - Action: restart worker process/pod, inspect job error channel, and replay retryable jobs.

5. **Stale RUNNING jobs**
   - Condition: any `RUNNING` job older than 30 minutes.
   - Severity: P1.
   - Action: cancel/requeue job and inspect exception logs before manual rerun.

6. **Retry saturation**
   - Condition: retry failures > 40 in 10 minutes.
   - Severity: P2.
   - Action: pause high-volume producer sources, drain/requeue with throttles.

### DB and migration integrity

7. **Migration drift**
   - Condition: migration version mismatch between runtime and tracked expected head.
   - Severity: P1.
   - Action: hold release gates, run migration status check, and execute rollback decision path.

8. **DB connection pool saturation**
   - Condition: pool utilization above 85% and wait-time increase over baseline for 10 minutes.
   - Severity: P1.
   - Action: scale app replicas (if needed), reduce burst traffic via throttles, inspect long locks.

## Incident runbooks

### A) Migration rollback (P1/P2)

1. Stop new deployments and freeze schema writes.
2. Confirm current migration head and target migration in DB history.
3. Notify impacted teams and estimate blast radius (users, active routes).
4. Decide rollback direction:
   - **Safe forward-fix** if migration is reversible with quick data fix.
   - **Rollback** if writes are unrecoverably blocking auth/read/write flow.
5. Run rollback/forward-fix command from release script with audit log capture.
6. Validate: health checks, run migration status check, and smoke read/write route check.
7. Monitor rollback window metrics and release lock before allowing write traffic again.

### B) Credential rotation (P1/P2)

1. Identify exposed credential family: `OKR_BACKEND_SERVICE_TOKEN`, `OKR_BACKEND_SIGNING_SECRET`, DB credentials, SMTP keys if used.
2. Notify on-call, security, and app owners.
3. Rotate in order: secret source -> service restart -> dependent clients -> verification sweep.
4. Confirm token parity by exercising one known read and one known mutation flow.
5. Invalidate old sessions/tokens where supported and clear stale caches.
6. Verify auth failure trend returns to baseline within 15 minutes.

### C) Worker dead-letter/retry recovery (P2/P1)

1. Freeze high-throughput producers to reduce retry amplification.
2. Identify failing job classes and exception families.
3. Classify each failure as retryable vs non-retryable.
4. Re-queue only retryable jobs after environment fix.
5. Mark non-retryable jobs for manual follow-up with data owner.
6. Re-enable production job throughput only after queue age returns to baseline.

## Operational simulation evidence checklist

- Verify dashboard coverage includes all required signal groups:
  - API, BFF, Worker, DB, Auth, Audit.
- Runbook smoke check:
  - Migration rollback runbook documented with rollback decision and validation steps.
  - Credential rotation runbook includes invalidation and verification steps.
  - Worker dead-letter/retry runbook includes retry classification and re-queue controls.
- Command evidence (for audits and drills):
  - Health probes (`/healthz`, DB migration status, queue depth).
  - Rollback drill dry-run in non-production.
  - Manual auth/key rotation exercise with scoped token refresh and recovery test.

Last updated: 2026-07-27
