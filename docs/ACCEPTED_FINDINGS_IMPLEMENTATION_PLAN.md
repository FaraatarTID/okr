Documentation HQ: [README](../README.md)

Accepted Findings Implementation Plan

Purpose
- Close all accepted security and architecture findings with production-safe defaults.
- Remove split ownership of write paths so authorization and business rules are enforced in one place.
- Add operational controls for throughput, stability, and AI/PDF spend.

Scope (Accepted Findings)
- F1: Privileged database connection can bypass defense-in-depth data isolation.
- F2: Split-brain mutation path (backend mutations plus Streamlit local fallback) can drift authorization logic.
- F3: Internal service-to-service auth should be stronger than network trust plus static token only.
- F4: Streamlit Cloud/local heavy fallback path can block under load.
- F5: SQLAlchemy pooling behavior should be aligned with Supabase PgBouncer transaction mode.
- F6: AI/PDF job submission lacks user/team quota controls (denial-of-wallet risk).

Target Architecture (Post-Remediation)
- `streamlit_app` is a UI client for reads and user interactions.
- `backend_api` is the only mutation authority for frontend write flows (node CRUD, timer, users/cycles/teams, Learning Loop writes, alignments, work-log deletes) and async jobs.
- `backend_worker` executes heavy AI/PDF jobs from queue.
- PostgreSQL access uses least-privilege app role via Supabase transaction pooler (`:6543`).
- Internal calls use token auth now, with request signing and private network policy hardening.

Workstream A: Database Privilege Hardening (F1)
Owner: Platform + Backend
Priority: P0
Tasks
- Create a dedicated non-superuser DB role for the app (`okr_app`) with least privilege.
- Revoke unnecessary grants from default/public roles and grant only required schema/table permissions.
- Rotate all app connection strings from `postgres` user to least-privilege role.
- Add startup guard in app/backends to reject superuser DSNs in non-dev environments.
- Update deployment docs/examples to prohibit `postgres` in runtime DSNs.
- Interim control note: if startup guard behavior is temporarily relaxed during incident response, production deployment still must enforce `okr_app` DSN usage via checklist/release gate (not optional).
Acceptance Criteria
- Runtime DSN user is not `postgres`.
- App startup fails in production mode if superuser DSN is supplied.
- CRUD, timer, and job flows still pass integration tests with least-privilege role.
- Release checklist explicitly verifies `okr_app` (or equivalent least-privilege role) before go-live.

Workstream B: Single Mutation Authority (F2, F4)
Owner: Backend + Streamlit
Priority: P0
Tasks
- Remove local mutation fallback for frontend mutation paths in production mode.
- Gate any emergency local fallback behind explicit non-production flag.
- Make backend availability a startup requirement for production profile.
- Ensure Streamlit Cloud mode is documented as non-production/demo only.
- Keep heavy operations (AI/PDF) asynchronous through backend API + worker only.
Acceptance Criteria
- All write operations go through `backend_api` in production.
- If backend is unavailable, write actions fail closed with clear user message (no local write path).
- No production route performs synchronous AI/PDF work in Streamlit process.

Workstream C: Internal Service Authentication Hardening (F3)
Owner: Security + Backend
Priority: P1
Tasks
- Keep `X-OKR-Service-Token` enforcement mandatory in production.
- Add HMAC request signing (`timestamp + nonce + body digest`) between Streamlit and backend API.
- Add replay window validation and nonce cache on backend API.
- Restrict backend API ingress to internal network/reverse proxy only.
- Document token/signing key rotation cadence and emergency revoke procedure.
Acceptance Criteria
- Unsigned or replayed internal requests are rejected with `401/403`.
- Backend API cannot be reached from untrusted network paths.
- Rotation runbook tested once in staging.

Workstream D: PgBouncer-Compatible DB Engine Configuration (F5)
Owner: Platform + Backend
Priority: P1
Tasks
- Switch SQLAlchemy engine to `NullPool` (or equivalent no-pool mode) when using Supabase transaction pooler.
- Keep app-level connection timeout and pre-ping configured for resilience.
- Validate no prepared-statement/session-state assumptions exist across requests.
- Document pooler requirements (`*.pooler.supabase.*:6543`) and forbidden direct-port production usage.
Acceptance Criteria
- No pool-related statement/session errors during concurrent test run.
- Connection counts remain stable under load.
- Configuration docs match runtime behavior.

Workstream E: AI/PDF Quotas and Spend Controls (F6)
Owner: Backend + Product Ops
Priority: P0
Tasks
- Add quota policy model (per-user and per-team): requests/minute, requests/day, and token/cost budgets.
- Enforce quotas before queue insertion in `backend_api`.
- Add idempotency key support for job submission endpoints to prevent duplicate clicks/retries.
- Add per-actor backoff and queue-size guardrails.
- Emit audit/usage events for every accepted/rejected job.
Acceptance Criteria
- Quota breach returns deterministic `429` with retry metadata.
- Duplicate submit with same idempotency key does not create extra jobs.
- Daily usage report can be generated per user/team.

Workstream F: Validation and Reliability Gates (F1-F6)
Owner: QA + Platform + Backend
Priority: P0
Tasks
- Add/extend tests for auth bypass attempts, IDOR cases, and split-path regression.
- Add integration tests that enforce backend-only mutation routing.
- Add UI runtime guard test to prevent non-submit Streamlit buttons inside forms (`st.button`/container `.button` inside `st.form`).
- Add mapper hot-reload guards: enforce consistent `src.models` import path, lambda-based relationship resolution, and stale-binding recovery tests.
- Run concurrency/load test for dashboard reads + timer actions + job submissions.
- Run chaos test: backend API restart, worker restart, transient DB/network blips.
- Run security verification checklist before pilot go-live.
Acceptance Criteria
- Test suite passes with new controls enabled.
- No form-widget runtime regressions in smoke tests (no `st.button() can't be used in an st.form()` failures).
- No SQLAlchemy duplicate-class/runtime mapper failures during app code hot-reload.
- No critical/high findings remain open in pre-go-live review.
- Pilot load profile meets latency/error-budget targets.

Execution Phases
1. Phase 0 (1-2 days): Baseline, branch protection, feature flags, and observability counters.
2. Phase 1 (3-5 days): Workstream A + D (DB role hardening and pooler-safe engine changes).
3. Phase 2 (4-6 days): Workstream B (backend-only mutation authority and production fail-closed behavior).
4. Phase 3 (3-4 days): Workstream E (quota, idempotency, and spend controls).
5. Phase 4 (2-3 days): Workstream C (request signing, replay protection, key rotation runbook).
6. Phase 5 (3-5 days): Workstream F (full validation, soak test, release checklist).

Definition of Done
- Production deployment path enforces least-privilege DB role, backend-only mutations, and internal request auth hardening.
- Supabase transaction pooler configuration is validated and documented as the only supported production DB connection mode.
- AI/PDF endpoints enforce quotas and idempotency and are observable with audit metrics.
- Documentation (`README`, deployment docs, config reference, checklists) reflects final architecture and operational procedures.
