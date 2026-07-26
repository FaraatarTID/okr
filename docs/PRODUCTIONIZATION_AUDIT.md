# Productionization Audit

Documentation HQ: [README](../README.md)

This audit treats the application as a fast prototype that must survive production load, security review, and ownership transfer. It is intentionally risk-focused and favors incremental hardening over a rewrite.

## Executive summary

The application is an OKR and strategic execution platform. It separates strategic change work from BAU operational work, provides an Atlas workspace for OKR execution, supports role-aware collaboration, records evidence/check-ins, runs AI analysis and PDF/report jobs, and exposes a SPA through a BFF to an internal FastAPI backend.

Readiness classification: **production risky for external or regulated use; usable as a controlled internal tool after deployment guardrails are enforced**.

Primary reasons:

- The system has clear intent and meaningful domain separation, but the runtime still carries prototype residue: a large Python CRUD facade, a very large backend API module, a large SPA shell component, legacy Streamlit/UI helper code, and multiple runtime modes.
- Security has improved materially through BFF mediation, service tokens, optional request signing, password rotation fields, RLS migrations, throttling, and audit events. Remaining risk is operational: configuration can silently degrade in non-production, secrets and internal service exposure depend on deployment discipline, and authorization needs continuous regression coverage.
- Reliability depends on PostgreSQL/Supabase, backend jobs, and polling. There are health and preflight scripts, but there is no complete SLO, alert, dashboard, or runbook ownership model.
- The current architecture can scale to a modest internal deployment. Scaling to 10x users requires reducing monolithic hot paths, tightening database access patterns, adding worker concurrency controls, and formalizing observability.

## Production readiness score

| Area | Score / 5 | Rationale |
| --- | ---: | --- |
| Architecture | 3 | SPA/BFF/API/worker split is directionally sound, but backend and SPA shell modules remain too large and runtime modes create hidden complexity. |
| Security | 3 | Good foundations exist; remaining risk is deployment/config enforcement, broad service token trust, and continuing RBAC regression discipline. |
| Reliability | 2 | Jobs and retries exist, but graceful shutdown, health checks, SLOs, and failure-mode documentation are incomplete. |
| Maintainability | 2 | Many tests and docs exist; giant files, compatibility paths, and split legacy/SPA surfaces raise change cost. |
| Scalability | 2 | PostgreSQL-backed model can grow, but Atlas snapshots, leadership metrics, jobs, and unbounded UI/API payloads need explicit limits and profiling. |
| Operations | 2 | Docker/Kubernetes docs exist; dashboards, alerting, runbooks, rollback procedure, and migration discipline need hardening. |
| **Overall** | **2.3 / 5** | Production-risky until operational controls, configuration validation, and refactoring of hot paths are completed. |

## Phase 1 — Application archaeology

### Application overview

The product manages strategic OKRs separately from BAU work. Users define Goals, Objectives, Key Results, Tasks, cycles, teams, check-ins, experiments, retrospectives, alignment links, and evidence updates. The core interaction surface is Atlas, a workspace that combines Focus Map, Focus Task, Inspector, rituals, leadership views, AI analysis, and report/PDF workflows.

### Users

- Members: update owned strategic work, run timers, check in on KRs, and provide evidence.
- Managers: govern cycles, coach teams, review risk, manage assigned OKRs, and run weekly rituals.
- Admin/operators: manage users, teams, deployment settings, backups, audits, and operational recovery.
- OKR transformation leads: use rollout, boundary, and playbook docs to enforce BAU/OKR separation.

### Core features

- OKR hierarchy: Cycle → Goal → Objective → Key Result → Task.
- Role-aware authentication and authorization.
- Atlas SPA workspace with focus map, inspector, timers, rituals, dashboard, timeline, weekly planning, and retrobox.
- Check-ins and learning loop workflows.
- Objective alignment graph and cross-hierarchy links.
- AI analysis for nodes/team health/strategy pulse, gated by external AI configuration.
- Async jobs for AI and PDF/report generation.
- Audit event persistence and summary queries.
- Docker Compose and Kubernetes deployment artifacts.

### Critical paths

1. Login and session creation through SPA/BFF/backend.
2. Atlas scope snapshot loading after login.
3. Goal/objective/KR/task mutations with ownership/RBAC enforcement.
4. KR check-ins and progress computation.
5. Timer start/stop and work-log integrity.
6. Manager/admin user, team, and cycle administration.
7. Async AI/PDF job submission, execution, polling, and failure handling.
8. Audit/event retention and operational investigation.
9. Database migrations and restore/import flows.

### Unknown areas

- Real production traffic profile: user count, cycles, hierarchy sizes, check-in frequency, and report usage are not encoded as capacity assumptions.
- Hosting target: Supabase transaction pooler is assumed in places, but local SQLite and Supabase REST fallback paths remain.
- Data classification: there is no explicit policy for sensitive employee performance data, AI prompt redaction, or retention beyond audit/job retention knobs.
- On-call ownership: deployment docs exist, but escalation paths and SLOs are not encoded.

### Risk areas

- Broad API module and CRUD facade make authorization regressions easy.
- Large Atlas shell component is a front-end change-risk hotspot.
- Multiple runtime modes and fallbacks create behavior drift between development and production.
- Async job backpressure exists but needs operational visibility and dead-letter policy.
- AI integration may leak sensitive strategic or personnel data if prompts are not governed.

## Phase 2 — Architecture review

### Current architecture diagram

```text
Browser
  |
  v
spa-web (Next.js UI)
  |
  v
spa-bff (Fastify public boundary: session, allowlist, proxy, signing)
  |
  v
backend-api (FastAPI internal control plane)
  |         \
  |          \ enqueue/poll
  v           v
PostgreSQL/Supabase <--- backend-worker (async AI/PDF jobs)
  ^                \
  |                 v
Alembic migrations   External AI providers / PDF renderers
```

### Frontend architecture

Current state: Next.js SPA with route pages, API client modules, tests, and an Atlas component hierarchy. The architecture has useful extraction into hooks and panels, but `AtlasShell.tsx` remains a 2k+ line orchestration component and `globals.css` is 1k+ lines.

Risk: Shell-level state, fetching, authorization display, and interaction orchestration can become too coupled. Future developers will struggle to safely alter Atlas without regression tests around state transitions.

### Backend architecture

Current state: FastAPI app with a very large `backend_app/main.py`, shared `src/crud.py` facade, domain modules, SQLModel models, Alembic migrations, and a separate worker process. This is viable as a modular monolith, but the API layer and CRUD facade are beyond comfortable size.

Risk: Endpoint growth will increase incidental coupling. Authorization, serialization, and transaction logic can be duplicated or bypassed.

### API design

Current state: BFF allowlists browser-facing calls and forwards to backend with service auth/signing support. Backend exposes versioned-ish internal endpoints and Pydantic schemas.

Risk: Public contracts need stricter versioning, request/response envelope consistency, idempotency coverage for all mutations, and payload limits.

### Database design

Current state: SQLModel tables, Alembic migrations, constraints, indexes, ownership/team fields, lifecycle states, audit events, async jobs, and RLS migration history.

Risk: schema evolution is active, but operational migration runbooks and query budget tests are thin. Hierarchical reads and leadership reports are likely hot paths.

### Authentication and authorization

Current state: User/password model with password hashes, token version, throttling, roles, manager/team ownership, service-token boundary, optional request signing, and RBAC tests.

Risk: This is not yet enterprise identity. SSO/OIDC, MFA, session revocation UX, admin action audit review, and secret rotation need planning before external customers.

### External integrations

Current state: AI providers and PDF renderers are optional/configurable. External AI is gated by environment configuration.

Risk: prompt/content policy, retry budgets, provider outage handling, and tenant/team data isolation are not visible enough.

### Background jobs

Current state: `async_job` table, backend worker, idempotency/rate limits, polling, result/error payload persistence, and pruning configuration.

Risk: table-backed jobs are acceptable for small deployments, but need concurrency leases, dead-letter handling, retry semantics, worker metrics, and queue-depth alerts.

### File/storage handling

Current state: PDF generation appears rendered on demand with fallback to HTML export; no large object store boundary is documented.

Risk: generated reports may become too large for DB/job payloads or request responses. Storage ownership and retention should be defined before growth.

### Caching/state management

Current state: UI caching helpers, cache tests, BFF sessions/cookies, and backend security state that can use memory/database/Redis.

Risk: memory security state in non-production can hide distributed-production issues. Cache invalidation and snapshot staleness need clearer contracts.

### Error handling

Current state: structured logger usage is documented, backend error/audit helpers exist, and fail-closed behavior is stated for backend transport failures.

Risk: client-visible errors, correlation IDs, retry hints, and alert classification are inconsistent until enforced as API conventions.

### Strengths

- Modular-monolith direction is appropriate; microservices are not necessary.
- SPA/BFF/internal API/worker split gives a real browser security boundary.
- Alembic migration history and SQL constraints indicate real persistence discipline.
- Test suite covers RBAC, backend security, jobs, database policy, and SPA components.
- Deployment artifacts exist for Compose and Kubernetes.

### Weaknesses

- Large files are active change hotspots: `backend_app/main.py`, `src/crud.py`, `src/crud_auth_helpers.py`, `src/models.py`, `src/database.py`, and `spa-web/src/components/AtlasShell.tsx`.
- Runtime behavior depends on many environment variables and fallbacks.
- Legacy Streamlit/UI helper code remains in `app.py` and `src/ui`, increasing the number of possible paths to reason about.
- Dependency versions are locked for Python but use semver ranges in Node manifests.
- Observability exists as components, not as an operated system.

### Architectural risks

- RBAC bypass from new endpoints calling lower-level helpers incorrectly.
- Snapshot/report endpoints becoming N+1 or unbounded-payload bottlenecks.
- Table-backed job queue contention under load.
- Drift between Supabase direct DB mode, Supabase REST API fallback mode, SQLite/local mode, Docker, and Kubernetes.
- AI data egress or prompt injection becoming a governance issue.

### Recommended future architecture

Keep a modular monolith:

- `spa-web`: UI only; move Atlas orchestration into feature modules with tested state machines/hooks.
- `spa-bff`: public boundary; keep allowlist, session, CSRF/cookie policy, request signing, and request-size limits here.
- `backend-api`: split route modules by domain (`auth`, `okr_tree`, `checkins`, `admin`, `jobs`, `reports`, `audit`) while sharing one process.
- `domain`: use service classes/functions that combine authorization + validation + persistence; avoid exposing raw CRUD to endpoints.
- `persistence`: retain SQLModel/Alembic; add repository/query modules for hot paths.
- `worker`: keep table-backed jobs initially; evolve to Redis/managed queue only when table contention is measured.
- `observability`: standardize JSON logs, metrics, tracing, SLO dashboards, and alerts.

## Phase 3 — Twelve-Factor audit

| Factor | Score | Current state and evidence | Risk | Recommended fix | Effort |
| --- | ---: | --- | --- | --- | --- |
| 1. Codebase | 3 | One repository contains SPA, BFF, backend, migrations, tests, docs, and deployment artifacts. Legacy Python UI files still coexist with SPA. | Medium | Declare SPA-first as canonical, mark legacy UI as deprecated or remove after migration; maintain CODEBASE_MAP ownership. | M |
| 2. Dependencies | 3 | Python pins exact versions; Node lockfiles exist, but manifests use `^` ranges. | Medium | Pin Node manifests or rely strictly on lockfile in CI/deploy; add recurring `npm audit`/`pip-audit` or equivalent. | S |
| 3. Configuration | 3 | Many env vars documented and loaded through runtime config; production behavior changes request signing/security backend defaults. | High | Add fail-fast production config validation covering DB URL, service token, signing secret, cookie security, AI egress, and public/internal origins. | M |
| 4. Backing services | 3 | PostgreSQL/Supabase, Redis optional, AI/PDF providers configurable. | Medium | Define backing service contracts and health checks; isolate provider retries/timeouts and credentials. | M |
| 5. Build / release / run | 2 | Dockerfiles, Compose, Kubernetes manifests, CI builds exist. Migration and rollback process is not enforceable. | High | Add release checklist, migration dry-run gate, rollback plan, immutable image tagging, and DB backup verification. | M |
| 6. Processes | 3 | API and worker are separate; BFF sessions are cookie-based; jobs persisted in DB. | Medium | Confirm no runtime file/session state; document worker restart semantics and idempotency per job type. | S |
| 7. Port binding | 4 | Services bind explicit ports; Compose exposes backend to loopback by default. | Low | Add `/healthz`, `/readyz`, and private-ingress checks consistently across API/BFF/web. | S |
| 8. Concurrency | 2 | Worker polling and rate limits exist; DB connection policy uses NullPool by default. | High | Add worker concurrency config, lease expiry, queue depth metrics, API payload/query limits, and load tests. | M/L |
| 9. Disposability | 2 | Startup initializes DB and admin; restart policy exists. Graceful shutdown and readiness semantics are incomplete. | Medium | Add signal-aware worker shutdown, transaction cancellation, readiness probes, and startup timeout tests. | M |
| 10. Dev/prod parity | 2 | Local SQLite and production Supabase/PostgreSQL modes differ; Supabase REST fallback adds another behavior path. | High | Make local dev use Postgres by default via Compose; reserve SQLite for unit tests only. | M |
| 11. Logging | 2 | Python logging, audit events, request IDs, and exception logging exist. Metrics/tracing/alerts are not first-class. | High | Standardize JSON logs, OpenTelemetry traces, RED/USE metrics, error tracking, and dashboard ownership. | M |
| 12. Admin processes | 3 | Alembic, backup/import helpers, deploy checks, and admin docs exist. | Medium | Add tested operational scripts for migrations, user recovery, job replay/cancel, audit export, and data retention. | M |

## Phase 4 — Code quality audit

### Critical

- No single enforceable production configuration gate blocks weak service tokens, missing signing secrets, insecure cookies, or accidental direct backend exposure.
- Authorization is distributed across many CRUD/helper paths and must remain a permanent regression focus.

### High

- `backend_app/main.py` is too large and mixes route registration, request plumbing, serialization, security handling, and business orchestration.
- `src/crud.py` is too large for safe ownership and hides many domain operations behind one facade.
- `spa-web/src/components/AtlasShell.tsx` is too large and centralizes too much UI state.
- `src/database.py` combines URL policy, engine creation, migrations, backup/import, JSON serialization, and direct DB health probing.
- `src/models.py` is a large shared model file with many domain concepts and mapper-reset side effects.

### Medium

- Legacy UI paths (`app.py`, `src/ui`) increase review surface and can confuse contributors.
- Multiple fallback modes create hidden assumptions in tests and operations.
- CSS size suggests global style coupling.
- Node dependency version ranges reduce reproducibility unless lockfiles are always honored.

### Low

- Some scripts are Windows batch files, which are useful locally but not meaningful for production automation.
- Documentation volume is high; navigation is good, but production operators need a shorter runbook index.

## Phase 5 — Security audit

### Authentication

Current strengths: password hashing, token versioning, throttle state, role model, and session mediation through BFF. Production gaps: no SSO/OIDC/MFA, password policy needs external review, and user lifecycle workflows are basic.

Recommended changes:

- Add OIDC/SAML option before external or enterprise deployment.
- Enforce password policy and rotation only where policy requires it; prefer MFA/OIDC over forced password churn.
- Add admin-visible session revocation and token-version bump workflow.

### Sessions and tokens

Current strengths: BFF session secret, secure cookie option, backend service token, optional signing/replay window.

Risks:

- Service token is broad; any BFF compromise can exercise the internal API within allowlist limits.
- Production safety depends on env correctness.

Recommended changes:

- Fail startup in production if service token/signing secret are absent or weak.
- Add request-size limits and CSRF policy documentation at BFF.
- Rotate service token/signing secret with dual-key support.

### Permissions

Current strengths: RBAC regression tests and domain authorization modules.

Risks:

- New endpoints can bypass actor-scoped read/mutation helpers.

Recommended changes:

- Require every route module to call a domain service that accepts actor context.
- Add endpoint-level authorization tests for every mutation.
- Add audit log review for admin and cross-team actions.

### Data security

Risks:

- OKR data may contain personnel performance details.
- AI prompts may send sensitive context externally.
- Backup encryption/retention is not explicitly governed.

Recommended changes:

- Classify data; define retention, export, deletion, and AI egress policy.
- Redact or minimize AI prompts; record provider/model/prompt metadata without storing sensitive full prompts unless explicitly allowed.
- Encrypt backups and document restore tests.

### Application security

Risks:

- API injection risk is reduced by SQLAlchemy/SQLModel but raw SQL and dynamic query helpers need review.
- Dependency vulnerability scanning is not shown in CI.
- Public/internal ingress separation is deployment-sensitive.

Recommended changes:

- Add dependency vulnerability gates.
- Add Semgrep/Bandit or targeted static checks for raw SQL, auth decorators, and secrets.
- Add an ingress test that proves backend API is not internet-exposed in production templates.

## Phase 6 — Database review

### Schema design

The schema models users, teams, cycles, OKR hierarchy, work logs, check-ins, experiments, alignment, async jobs, auth throttle state, and audit events. It includes constraints and indexes through migrations.

### Potential scaling problems

- Hierarchy snapshots can become large and expensive as cycles/teams grow.
- Leadership metrics can aggregate across large task/check-in histories.
- `async_job` and `audit_event` tables will grow continuously without partitioning/retention enforcement.
- NullPool with high API concurrency can stress PgBouncer/DB if request fan-out is high.
- RLS policy performance must be profiled with realistic team sizes.

### Data risks

- SQLite/local behavior can mask PostgreSQL constraints, isolation, and query plans.
- Backups/imports need encryption and restore validation.
- AI result/error payloads stored in jobs may contain sensitive data.
- Deletions and ownership transfers need clear audit semantics.

### Recommended improvements

- Add query-budget tests for Atlas snapshot, leadership metrics, audit summary, and job polling.
- Add indexes based on real `EXPLAIN ANALYZE`, not guesses.
- Enforce retention pruning for async jobs and audit events; consider partitioning audit events before high volume.
- Prefer Postgres in local Compose to improve parity.
- Add migration dry-run and rollback documentation per release.

## Phase 7 — Testing audit

### Current coverage

- Unit/integration tests exist across backend, RBAC, jobs, security state, database policy, audit, cache, deadline, and SPA components.
- SPA BFF has focused TypeScript tests.
- SPA web has component/hook tests and coverage script.
- Playwright E2E exists for login to Atlas.

### Critical paths without enough confidence

- Full manager/admin workflow from user creation to cycle management to cross-team OKR governance.
- Production configuration failure modes.
- Migration upgrade/downgrade on realistic data.
- AI/PDF provider outages and timeout behavior.
- Worker crash/restart during job execution.
- Atlas large-cycle performance at 10x data.

### Testing recovery plan

#### Week 1

- Add production-config fail-fast tests.
- Add route authorization matrix tests for every mutation endpoint.
- Add worker restart/idempotency tests for job claim and retry behavior.
- Add smoke test for Compose startup with Postgres.

#### Month 1

- Add migration tests using a seeded production-like fixture.
- Add API contract tests between SPA BFF and backend schemas.
- Add Atlas performance tests for large snapshots.
- Add failure-injection tests for AI/PDF timeouts and DB transient errors.

#### Long term

- Add nightly E2E covering member, manager, and admin journeys.
- Add load tests for Atlas snapshot, check-ins, leadership metrics, and job submission.
- Add security regression automation for secrets, auth bypass, and dependency CVEs.

## Phase 8 — Observability review

Can engineers answer operational questions today?

| Question | Current answer | Gap |
| --- | --- | --- |
| Is the system healthy? | Partially, through logs/scripts and service startup. | Need health/readiness endpoints and dashboards. |
| What failed? | Partially, through logs, audit events, and job errors. | Need structured error taxonomy and alert routing. |
| Why did it fail? | Sometimes, if logs include correlation IDs and exceptions. | Need tracing across web/BFF/API/worker/DB/provider. |
| Which users were affected? | Audit events may help. | Need request/user/team correlation and privacy-safe impact queries. |
| How long did recovery take? | Not first-class. | Need incident timeline metrics and SLO tracking. |

Recommended observability baseline:

- JSON logs across BFF/API/worker with request ID, correlation ID, actor, route, status, latency, team/cycle scope where safe.
- Metrics: request rate/error/duration, DB query latency, job queue depth, job age, job success/failure, worker heartbeats, AI/PDF provider latency/error, auth failures, rate-limit events.
- Tracing: OpenTelemetry from BFF → API → DB/provider/worker job execution.
- Alerts: elevated 5xx, auth anomaly, job backlog, worker down, DB latency, AI/PDF outage, migration failure, audit prune failure.
- Dashboards: executive uptime, API performance, worker queue, database, security events, AI/PDF providers.

## Phase 9 — Scalability review

At 10x users, 10x data, 10x traffic, and multiple developers:

### Bottlenecks

- Atlas snapshot payload size and computation.
- Leadership metrics and check-in freshness queries.
- DB-backed async jobs and polling frequency.
- Large frontend shell state causing re-render and regression cost.
- Broad backend API module creating merge conflicts and review bottlenecks.

### Architectural limits

- Table-backed queue is acceptable until contention and polling overhead dominate.
- Single database is correct for now, but read-heavy analytics may need materialized summaries.
- No microservices should be introduced until module boundaries and metrics prove a need.

### Expensive operations to profile

- Scope snapshot build.
- Goal tree reads.
- Leadership metrics.
- Audit summaries.
- Alignment graph cycle detection and context queries.
- Job polling at high active-user counts.

### Scaling blockers

- Lack of production-like load tests and query budgets.
- Insufficient observability for saturation diagnosis.
- Unbounded or weakly bounded request/response payloads.
- Unclear data retention for audit/jobs/reports.

## Phase 10 — Refactoring roadmap

### Immediate (0–7 days)

1. Problem: Production can start with unsafe or incomplete config.  
   Why it matters: weak service boundaries create security incidents.  
   Proposed change: add fail-fast `validate_production_settings()` across backend and BFF.  
   Expected benefit: prevents accidental insecure deployment.  
   Risk: may break existing ad hoc deployments.  
   Effort: M.

2. Problem: Backend API may be accidentally exposed.  
   Why it matters: service token/signing are internal controls, not a public API product.  
   Proposed change: add deployment smoke test and docs requiring private backend ingress.  
   Expected benefit: reduces internet exposure risk.  
   Risk: deployment templates must be updated.  
   Effort: S.

3. Problem: No clear top-level productionization backlog.  
   Why it matters: future engineers need prioritized work, not scattered docs.  
   Proposed change: adopt this audit as a tracked modernization plan.  
   Expected benefit: clear sequencing.  
   Risk: document can stale unless owned.  
   Effort: S.

4. Problem: Authorization changes are high-risk.  
   Why it matters: OKR data is people/team sensitive.  
   Proposed change: require endpoint authorization tests for every new mutation.  
   Expected benefit: catches regressions before merge.  
   Risk: test maintenance.  
   Effort: S.

### Short term (1–4 weeks)

1. Problem: API module is too large.  
   Proposed change: split `backend_app/main.py` into routers by domain without changing external routes.  
   Expected benefit: lower merge conflicts and safer reviews.  
   Risk: import cycles.  
   Effort: M.

2. Problem: CRUD facade is too broad.  
   Proposed change: introduce domain service modules that combine actor context, validation, transactions, and audit.  
   Expected benefit: fewer bypass paths.  
   Risk: duplicated logic during transition.  
   Effort: M/L.

3. Problem: Atlas shell is a UI hotspot.  
   Proposed change: extract state machines/hooks for selection, mode, timer, snapshot loading, and inspector mutations.  
   Expected benefit: easier UI changes with tests.  
   Risk: behavior drift.  
   Effort: M.

4. Problem: Observability lacks dashboards/alerts.  
   Proposed change: implement metrics and log schema, then add dashboards for API/worker/DB/provider.  
   Expected benefit: faster incident detection.  
   Risk: instrumentation noise.  
   Effort: M.

### Medium term (1–3 months)

1. Problem: Query and payload costs are unknown.  
   Proposed change: add performance harness and budgets for snapshots, metrics, audit summaries, and job polling.  
   Expected benefit: measurable scalability.  
   Risk: fixture quality.  
   Effort: M.

2. Problem: Worker queue semantics are underspecified.  
   Proposed change: add leases, dead-letter policy, retry classes, queue metrics, and worker graceful shutdown.  
   Expected benefit: reliable async execution.  
   Risk: schema changes.  
   Effort: M.

3. Problem: AI governance is incomplete.  
   Proposed change: implement prompt minimization, provider allowlist, data classification, and audit metadata.  
   Expected benefit: reduced data egress risk.  
   Risk: weaker AI context unless designed carefully.  
   Effort: M.

4. Problem: Local/prod parity differs.  
   Proposed change: make Postgres Compose the default local path; keep SQLite only for fast tests.  
   Expected benefit: fewer production surprises.  
   Risk: local setup friction.  
   Effort: M.

### Long term

1. Problem: Analytics/reporting may overload transactional reads.  
   Proposed change: add materialized summaries or read models if metrics prove pressure.  
   Expected benefit: predictable leadership dashboards.  
   Risk: eventual consistency complexity.  
   Effort: L.

2. Problem: Enterprise auth is missing.  
   Proposed change: add OIDC/SAML and optional SCIM only when customer/user base requires it.  
   Expected benefit: safer identity lifecycle.  
   Risk: identity integration complexity.  
   Effort: L.

3. Problem: Single team ownership model may not fit larger organizations.  
   Proposed change: evolve permissions to explicit memberships/scopes if manager/team hierarchy becomes insufficient.  
   Expected benefit: better enterprise fit.  
   Risk: migration and UX complexity.  
   Effort: L.

## Top 10 actions before scaling

1. Add fail-fast production configuration validation.
2. Prove backend API is private in deployment templates and smoke tests.
3. Add endpoint-level authorization matrix tests for all mutations.
4. Split `backend_app/main.py` into domain routers.
5. Create domain service layer around actor-scoped operations and transactions.
6. Add observability baseline: JSON logs, metrics, traces, dashboards, alerts.
7. Add query/payload performance budgets for Atlas snapshots and leadership metrics.
8. Harden async worker semantics: leases, graceful shutdown, dead-letter/retry policy.
9. Define AI/data egress policy and prompt minimization.
10. Make Postgres the default local integration environment.

## If this was my company

I would fix production configuration validation and private-ingress proof first because those prevent avoidable security incidents. Next I would strengthen endpoint authorization tests and split the oversized backend API into routers, because the most likely damaging future bug is a well-intentioned feature that bypasses RBAC or mutates the wrong scope. In parallel, I would add metrics and worker queue alerts because silent async failure will damage trust quickly.

I would deliberately leave microservices, a new database, and a full frontend rewrite alone. The current modular-monolith shape is the right level of complexity. I would also keep table-backed jobs until real queue contention is measured. The goal is to preserve working OKR business logic while making failures visible, configuration safe, and future changes reviewable.
