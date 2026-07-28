# Production Readiness Audit
Documentation HQ: [README](../README.md)

Date: 2026-07-27

This audit treats the repository as an inherited system that must be operated, modified, and scaled without relying on prototype-era context.

## Executive Summary

The application is an OKR and strategy-execution workspace that separates strategic change work from BAU operational work. It includes a Next.js SPA, a Fastify BFF, a FastAPI backend API, a backend worker, SQLModel/PostgreSQL persistence, Alembic migrations, and optional AI/PDF integrations.

Readiness classification: **production risky, but recoverable through incremental hardening**. The repository has moved beyond a throwaway prototype: it has migrations, tests, deployment assets, auth/RBAC concepts, background jobs, observability primitives, and documented topology. It is not yet comfortably scalable because key ownership and operational boundaries remain too concentrated in large modules, runtime behavior depends on many environment flags, the SPA/BFF/backend split increases release complexity, and the database model carries broad business logic coupling.

Production readiness score: **3.0 / 5**.

| Area | Score | Rationale |
| --- | ---: | --- |
| Architecture | 3.0 | Clear service topology exists, but backend and domain boundaries remain partially coupled. |
| Security | 3.2 | Strong intent around BFF boundary, service tokens, request signing, password policy, and RLS migration; needs external verification and secret management maturity. |
| Reliability | 2.8 | Durable jobs and health endpoints exist; graceful shutdown, rollback playbooks, SLOs, and failure-mode tests are incomplete. |
| Maintainability | 2.7 | Tests are extensive, but several giant modules and duplicated proxy/direct modes create change risk. |
| Scalability | 2.6 | PostgreSQL-centric design can scale to moderate load; horizontal behavior depends on DB/Redis-backed state and careful pooler configuration. |
| Operations | 2.8 | Docker/Kubernetes assets and deploy checks exist; observability, runbooks, dashboards, and admin process ergonomics need work. |

## Phase 1 — Application Archaeology

### Product Understanding

Problem solved: the product provides a strategy cockpit for OKRs, forcing measurable outcome evidence and keeping BAU work out of strategic reporting.

Users:

- Members who own tasks, check in on key results, and use timers.
- Managers who review team scope, assign/coach OKRs, and run weekly governance.
- Admin/operators who manage users, teams, cycles, deployment, and system health.
- Transformation or leadership users who inspect rollups, risks, alignments, and learning-loop outputs.

Critical user journeys:

1. Login through the BFF and establish a browser session.
2. Select a cycle and navigate Atlas.
3. Create or update goals, objectives, key results, and tasks.
4. Start/stop a focus-task timer and record work logs.
5. Submit check-ins that update KR progress and evidence.
6. Review leadership metrics, stale check-ins, deadline health, and audit summaries.
7. Run AI analysis or PDF weekly reporting through durable backend jobs.
8. Administer teams, users, roles, passwords, and active cycles.

Core business workflows:

- Strategic hierarchy management: Cycle -> Goal -> Objective -> Key Result -> Task.
- Evidence and scoring: KR metric movement, objective/goal rollups, confidence and risk.
- Governance loop: weekly plans, retrospectives, experiments, outcomes, and audits.
- Alignment loop: objective-to-objective and objective-to-goal/KR links with cycle protection.
- Operational boundary: BAU work is explicitly kept outside the app.

Mission-critical areas:

- Authentication/session validity and token-version revocation.
- Authorization for mutation and read scope.
- Database integrity and migrations.
- Timer/work-log correctness.
- Check-in and KR progress mutation correctness.
- Async job idempotency/rate limiting.
- Audit logs for security-sensitive and governance actions.

### Application Overview

The primary runtime is a SPA-first web application. Browser traffic reaches `spa-web`, authenticated browser API calls pass through `spa-bff`, and service-authenticated requests reach `backend-api`. Heavy work is executed by `backend-worker` using durable `async_job` records. Persistence is PostgreSQL/Supabase with SQLModel models and Alembic migrations.

### Core Features

- OKR hierarchy CRUD and lifecycle states.
- User/team/cycle administration.
- Role-aware reads and mutations.
- Timer and work-log tracking.
- Check-ins, weekly planning, retrospectives, experiments, and outcomes.
- Alignment graph and cross-hierarchy links.
- AI analysis and PDF generation.
- Audit event persistence and summarized audit queries.
- Deployment checks for backend-private topology and production config.

### Critical Paths

- Login/session/me: BFF cookie session, CSRF token, backend validation.
- Mutation path: SPA -> BFF allowlist -> FastAPI route -> authorization -> SQLModel session -> commit.
- Read path: SPA -> BFF -> backend read query -> SQLModel/Supabase API mode -> serialized view.
- Job path: submit -> rate/idempotency checks -> `async_job` -> worker claim/execute -> poll result.
- Timer path: start/stop with ownership gating and unique open work-log constraint.

### Unknown Areas

- Actual production hosting platform and secret manager are not represented as code.
- Backup/restore schedule, RPO/RTO, and disaster-recovery drills are not explicit.
- SLOs, alert thresholds, dashboards, and on-call runbooks are not defined.
- Real data volume, tenant count, traffic shape, and AI/PDF usage patterns are unknown.
- Accessibility, browser support, and internationalization acceptance criteria are not audited here.

### Risk Areas

- Large modules (`backend_app/main.py`, `src/services/supabase_api_mode.py`, `src/crud.py`) concentrate behavior and increase regression risk.
- Multiple data access modes (direct PostgreSQL and Supabase REST fallback) can diverge.
- Runtime configuration is powerful but high-dimensional; bad combinations can pass local testing.
- Operational reliability relies heavily on database semantics; Redis/database-backed shared state must be mandatory for horizontal production.
- AI/PDF integrations create data-egress, latency, cost, and failure-mode risks.

## Phase 2 — Architecture Review

### Current Architecture Diagram

```mermaid
flowchart LR
  Browser[Browser] --> Web[Next.js spa-web]
  Web --> BFF[Fastify spa-bff]
  BFF --> API[FastAPI backend-api]
  API --> DB[(PostgreSQL / Supabase)]
  API --> Jobs[(async_job table)]
  Worker[backend-worker] --> Jobs
  Worker --> DB
  API --> AI[AI provider / gateway]
  Worker --> AI
  API --> PDF[PDFShift or Chromium]
  BFF --> Session[Signed cookies + CSRF]
```

### Frontend Architecture

Current state: Next.js SPA with local test setup and BFF-mediated API calls. The architecture intentionally keeps service secrets out of the browser and routes mutations through backend APIs.

Concerns:

- State ownership is partly documented but must remain enforced through component boundaries and regression tests.
- The frontend package has a single visible test file at shallow depth; critical UX journeys need broader component and E2E coverage.
- Dependency versions use caret ranges despite a lockfile, which is acceptable for application installs but should be treated carefully in CI.

### Backend Architecture

Current state: FastAPI backend API plus worker. Routes are partially modularized under `backend_app/routers`, while many handler implementations and imports still aggregate in `backend_app/main.py`. Shared business logic lives under `src/` with `crud.py` as a facade and domain modules for authorization, analytics, scoring, lifecycle, reads, and progress.

Concerns:

- `backend_app/main.py` remains a large orchestration hotspot.
- CRUD/domain/service layering is real but incomplete; some integration code still knows too much about persistence and fallback behavior.
- Supabase REST fallback paths can create a second implementation of business behavior.

### API Design

Current state: Versioned `/v1` backend API, BFF allowlisting, service token auth, optional request signing, idempotency support for jobs, and token-version session validation.

Concerns:

- API contracts should be generated or documented from schemas, not inferred from tests and handlers.
- Error responses need a consistent public error envelope and stable error codes across BFF/backend.
- Compatibility policy for `/v1` changes is not documented.

### Database Design

Current state: SQLModel models, Alembic migrations, FKs/check constraints/indexes, async jobs, audit events, auth throttle state, alignment entities, teams/users/roles, lifecycle states.

Concerns:

- SQLModel metadata reset in `models.py` is an import-time smell that may mask module lifecycle problems.
- JSON payload/result fields in `async_job` are flexible but limit queryability and validation.
- Some uniqueness/index behavior is dialect-specific and must be continuously tested against PostgreSQL, not only SQLite.

### Authentication and Authorization

Current state: password hashes, roles, managers, teams, BFF session cookies, CSRF, token-version invalidation, backend service access, request signing, and authorization domain modules.

Concerns:

- Need production-grade password reset/invite flow, audit review, and explicit lockout operations.
- Need external penetration testing around BFF allowlist, forwarded IP handling, CSRF, and direct backend exposure.

### External Integrations

- AI providers are policy-gated by env flags and provider configuration.
- PDF generation supports PDFShift and Chromium.
- Supabase PostgreSQL and optional Supabase REST API mode are core platform dependencies.

### Background Jobs

Current state: durable `async_job`, backend worker, rate limits, pending limits, idempotency key, pruning settings, and worker observability tests.

Risk: job execution lacks a visible dead-letter queue, operator retry UI, and per-kind resource budgets beyond rate limiting.

### File / Storage Handling

Current state: backup import/export and PDF/HTML export exist. No large object store abstraction is evident.

Risk: backup uploads are allowed through the BFF with a 50 MB body limit; production needs explicit storage, retention, encryption, and malware/content handling policies if this grows.

### Caching Strategy

Current state: runtime cache helpers exist for Atlas snapshots and app-cycle caching; database remains source of truth.

Risk: cache invalidation and cross-process behavior must be documented and tested under multiple workers.

### State Management

Current state: BFF owns browser session cookies/CSRF; backend security state can use memory, database, or Redis; app state should be database/Redis in production.

Risk: memory-backed state is unsafe for horizontal production and must be blocked in production deploys.

### Error Handling

Current state: backend and BFF log exceptions and return generic messages in several paths. Observability context and audit logging exist.

Risk: inconsistent error envelope and missing correlation ID propagation to client-facing errors slow incident response.

### Strengths

- Service boundaries are explicit and avoid exposing backend service tokens to the browser.
- Migrations and tests show deliberate hardening work.
- Durable job records provide a better foundation than in-process background tasks.
- Security controls include service tokens, signing, CSRF, token-version revocation, rate limiting, and deployment checks.

### Weaknesses

- Large modules still hide behavior and make ownership unclear.
- Runtime modes and fallbacks multiply test matrix size.
- Operational docs are deployment-heavy but not incident/runbook-heavy.
- API contracts and data contracts are not first-class generated artifacts.

### Architectural Risks

- Divergence between direct DB mode and Supabase API mode.
- Production-only failures from environment combinations not covered by tests.
- Scaling blockers from DB-backed coordination if indexes/pruning are insufficient.
- Security regressions from expanding allowlists or mutation routes without generated policy checks.

### Recommended Future Architecture

Keep the current modular monolith plus BFF and worker. Do not introduce microservices. Move toward:

- Thin FastAPI route modules with handlers delegated to domain/application services.
- One authoritative data access path per business capability; remove or strictly quarantine fallback duplicates.
- Generated OpenAPI + client contract tests between BFF and backend.
- Mandatory distributed security state for production.
- Explicit operational layer: runbooks, dashboards, alerts, migration playbooks, backup restore drills.

## Phase 3 — Twelve-Factor Application Audit

| Factor | Score | Current state and evidence | Risk | Recommended fix | Effort |
| --- | ---: | --- | --- | --- | --- |
| 1. Codebase | 3 | One repo contains SPA, BFF, backend, worker, migrations, deploy assets, docs, and tests. Some Windows launcher scripts and backlog/docs add noise. | Medium | Add ownership map enforcement, archive obsolete scripts, keep `CODEBASE_MAP.md` current, add repo navigation section for new maintainers. | S |
| 2. Dependencies | 3 | Python dependencies are pinned; Node has lockfiles but package manifests use semver ranges. | Medium | Add Dependabot/Renovate, vulnerability scanning, license checks, and unused dependency audits. | S-M |
| 3. Configuration | 3 | Config is env-driven with validation for backend/BFF production settings. | Medium | Centralize config reference into generated schema; fail startup on unknown dangerous combinations; require secrets from a manager in production. | M |
| 4. Backing Services | 3 | PostgreSQL/Supabase, Redis option, AI, PDF, and external API modes are configurable. | Medium | Define abstraction boundaries and production support tiers for each backing service; add service health checks and timeout budgets. | M |
| 5. Build / Release / Run | 2 | Docker/Kubernetes assets exist; migrations exist; rollback/release promotion is not fully codified. | High | Add CI pipeline, immutable image tags, migration preflight, release manifest, and rollback runbook. | M |
| 6. Processes | 3 | App is mostly stateless if sessions/security state are shared; jobs are durable. | Medium | Block memory state in production; add worker concurrency and idempotency runbooks. | S-M |
| 7. Port Binding | 4 | FastAPI, Fastify, and Next.js are independently runnable services with health endpoints. | Low | Document exact ports, private/public ingress, and readiness semantics per service. | S |
| 8. Concurrency | 2 | Horizontal scale is plausible but depends on DB/Redis state and careful row locking. | High | Add load tests, multi-worker tests, queue-depth alerts, and DB pooler validation in CI. | M-L |
| 9. Disposability | 2 | Startup validation exists; graceful shutdown and recovery drills are not obvious. | Medium | Add SIGTERM handling verification, readiness/liveness probes, worker lease expiry tests, and startup timing budgets. | M |
| 10. Dev/Prod Parity | 2 | Docker Compose and K8s manifests exist; local SQLite/test modes can diverge from PostgreSQL behavior. | Medium | Add PostgreSQL-backed integration profile in CI and local compose; document parity exceptions. | M |
| 11. Logging | 3 | Structured backend logging, audit events, and metrics snapshot exist. | Medium | Standardize JSON logs across BFF/backend/worker; add tracing, dashboards, and alerts. | M |
| 12. Admin Processes | 2 | Alembic and scripts exist; operational one-off workflows are not packaged. | Medium | Add CLI admin commands for user recovery, job retry/cancel, audit export, backup restore test, and data fixes. | M |

## Phase 4 — Code Quality Audit

### Critical

- No critical code-quality defect was proven from static inspection alone; critical findings require runtime/security validation.

### High

- `backend_app/main.py` is still too large and import-heavy, which increases conflict and regression risk.
- `src/services/supabase_api_mode.py` duplicates substantial behavior and can drift from direct DB behavior.
- `src/crud.py` remains a broad facade that can become a dumping ground for unrelated business rules.
- API error handling is not visibly normalized across all routes.

### Medium

- SQLModel metadata reset at import time is fragile and should be isolated to test/runtime bootstrap if still needed.
- Configuration is spread across Python, TypeScript, deploy scripts, and docs.
- Test suite is broad but frontend and browser journeys are comparatively thin.
- Some deployment scripts are platform-specific `.bat` files that should not be primary operational automation.

### Low

- Documentation is abundant but can become stale because architecture, backlog, deployment, and guides overlap.
- Naming mixes product concepts (`Atlas`) and generic backend/service names; this is manageable but needs a glossary in code ownership docs.

## Phase 5 — Security Audit

Authentication:

- Password hashes and password rotation fields exist.
- BFF signs session cookies and issues CSRF cookies.
- Backend validates current user and token versions.
- Auth throttle state exists.

Authorization:

- Roles include admin, manager, member.
- Authorization domain modules and mutation authorization matrix tests exist.
- Risk remains around read-scope consistency and future route additions.

Data security:

- Runtime DSN policy discourages superuser and direct non-pooler Supabase connections when strict mode is enabled.
- Secrets are env-driven and examples use placeholders.
- Production must use a real secret manager and rotation process.

Application security:

- BFF allowlisting and backend-private deploy checks reduce exposed surface.
- Request signing and service tokens reduce direct backend abuse.
- Body size limit exists in BFF, but backup import/export needs a stricter operational policy.
- Dependency vulnerability scanning must be automated.

Security recommendations:

1. Make distributed security state mandatory in production.
2. Add OpenAPI route inventory to compare mutation routes, allowlist entries, auth requirements, and tests.
3. Add dependency/security scans to CI.
4. Run PostgreSQL RLS and authorization tests against a real PostgreSQL database.
5. Add a documented incident process for credential compromise, token rotation, and session invalidation.

## Phase 6 — Database Review

Schema design:

- Core hierarchy and support tables are present.
- Migrations include lifecycle, alignment, performance indexes, integrity constraints, RLS, async jobs, audit events, teams, ownership, and token version.

Indexing:

- Models define indexes for users, async jobs, audit events, throttle state, and common ownership fields.
- Need query-plan validation under production-like data.

Migrations:

- Alembic is present and migration history is non-trivial.
- Need zero-downtime migration discipline: expand/migrate/contract, backfill batching, lock-time budgets.

Query performance:

- Dedicated analytics/read query modules exist.
- Risk remains in hierarchical traversals, leadership rollups, stale check-in scans, and audit summaries as data grows.

Data integrity:

- FK/check constraints and lifecycle validations exist.
- Need periodic integrity audits and production constraint drift checks.

Transaction handling:

- SQLModel sessions and commits are used broadly.
- Need explicit transaction boundaries per command and idempotency guarantees for retried mutations.

Potential Scaling Problems:

- Leadership metrics and Atlas snapshots may become expensive with 10x data.
- `async_job` and `audit_event` tables need partitioning or aggressive retention if traffic increases.
- Database-backed rate/security state can become hot without Redis or careful indexing.

Data Risks:

- Backup import/export can damage data if not isolated behind admin-only controls and restore drills.
- JSON job payloads/results may store sensitive prompts or user content without clear retention classification.
- Supabase API fallback can bypass assumptions made in direct SQL paths if not kept equivalent.

Recommended Improvements:

- Add PostgreSQL integration tests for migrations, constraints, and query plans.
- Add table-size, index-bloat, slow-query, and lock monitoring.
- Define retention for audit events, jobs, backups, and AI/PDF artifacts.
- Add migration review checklist and rollback plan per release.

## Phase 7 — Testing Audit

Current coverage:

- Unit/integration tests: substantial Python backend/domain coverage.
- BFF tests: present for server/config/proxy/session behavior.
- E2E tests: at least one Playwright SPA login-to-Atlas test exists.
- Regression tests: many bug-specific tests exist for security, timer, backend config, date handling, and performance hot paths.

Critical paths without enough tests:

- Full browser happy path across create/update/check-in/timer/AI job/PDF.
- Real PostgreSQL migration and RLS behavior.
- Multi-worker concurrency and job claim contention.
- Production deployment validation in an environment close to the real host.
- Failure-mode tests for AI/PDF provider timeouts and partial outages.

Testing Recovery Plan:

Week 1:

- Add a smoke test script that starts SPA+BFF+backend+worker using Docker Compose and verifies login, health, mutation, read, and job submit/poll.
- Add CI jobs for Python tests, BFF tests, SPA typecheck, deploy config checks, and dependency audit.
- Mark all production-critical tests with stable markers.

Month 1:

- Add PostgreSQL-backed integration tests for Alembic upgrade, authorization, RLS, and performance indexes.
- Expand Playwright E2E coverage for core user journeys.
- Add contract tests generated from OpenAPI and BFF allowlist.
- Add chaos/failure tests for backend unavailable, worker crash, DB timeout, AI timeout, and PDF renderer missing.

Long Term:

- Add load tests for 10x users/data/traffic.
- Track coverage by critical path, not only by line count.
- Add mutation testing or property tests around scoring/progress/deadline logic.
- Add production synthetic checks for health, login, read snapshot, and background job execution.

## Phase 8 — Observability Review

Can engineers answer "Is the system healthy?" Partially. Health endpoints and metrics snapshots exist, but service-level dashboards and alert definitions are not first-class.

Can engineers answer "What failed?" Partially. Logs and audit events help; consistent correlation IDs across browser/BFF/backend/worker must be guaranteed.

Can engineers answer "Why did it fail?" Weak to partial. Tracebacks exist in backend logs, but distributed traces and dependency-level metrics are needed.

Can engineers answer "Which users were affected?" Partial. Audit events include actor and target context; request traces and user-impact dashboards are needed.

Can engineers answer "How long did recovery take?" Weak. Incident timelines and SLO burn tracking are not documented.

Recommendations:

- Logs: JSON logs across all services with request ID, correlation ID, actor, route, status, latency, and error code.
- Metrics: request count/latency/error rate, DB query latency, worker queue depth, job age, job failure rate, auth failures, rate-limit hits, AI/PDF latency/cost.
- Alerts: API 5xx, BFF 5xx, login failure spike, queue age, stuck jobs, DB connection errors, migration failure, backup failure, audit anomaly.
- Tracing: OpenTelemetry from BFF to backend to DB/job worker and external calls.
- Dashboards: executive health, API health, worker health, auth/security, database health, cost/AI usage.

## Phase 9 — Scalability Review

At 10x users, 10x database size, and 10x traffic, the primary bottleneck will be database read/write patterns and worker queue throughput, not the HTTP frameworks.

Bottlenecks:

- Atlas snapshot and leadership rollup queries.
- Audit and async-job table growth.
- DB-backed security state and rate limits under high traffic.
- PDF/AI job latency and external provider quotas.
- Large BFF backup uploads.

Architectural limits:

- Direct DB and Supabase API fallback create operational complexity.
- In-memory state is incompatible with horizontal production.
- Large route/facade modules slow multi-developer change.

Expensive operations:

- Hierarchical tree reads.
- Alignment cycle checks.
- Audit summaries over time windows.
- AI analysis prompts with large alignment context.
- PDF rendering.

Scaling blockers:

- Missing load-test baseline and query plans.
- Missing formal retention/partitioning plan.
- Missing generated API contract and route ownership enforcement.
- Incomplete runbooks for worker failure, migration rollback, and credential rotation.

## Phase 10 — Refactoring Roadmap

### Immediate (0-7 days)

1. Problem: Production state can be accidentally memory-backed. Why it matters: sessions, replay protection, and rate limiting break under multiple instances. Proposed change: block memory security state in production deploy checks and startup validation. Expected benefit: safe horizontal baseline. Risk: local config friction. Effort: S.
2. Problem: No single operational smoke test. Why it matters: deploys can pass unit tests while service wiring fails. Proposed change: add Docker Compose smoke test for login, health, read, mutation, job. Expected benefit: catches topology regressions. Risk: CI runtime increase. Effort: M.
3. Problem: Route/auth/allowlist drift is easy. Why it matters: new APIs may bypass intended security. Proposed change: generated route inventory test comparing backend routes, BFF allowlist, and auth matrix. Expected benefit: prevents accidental exposure. Risk: initial false positives. Effort: M.
4. Problem: Dependency vulnerabilities are not automatically surfaced. Why it matters: supply-chain risk. Proposed change: add `pip-audit`/`npm audit` or equivalent CI gate with documented exceptions. Expected benefit: known exposure window shrinks. Risk: noisy advisories. Effort: S.

### Short Term (1-4 weeks)

1. Problem: `backend_app/main.py` remains an ownership hotspot. Why it matters: high merge conflict and regression risk. Proposed change: move handler implementations into application-service modules by domain. Expected benefit: smaller diffs, clearer testing. Risk: route behavior changes if rushed. Effort: L.
2. Problem: Error responses are inconsistent. Why it matters: clients and operators cannot reason about failures. Proposed change: standard error envelope with code/message/request_id/details. Expected benefit: better UX and support. Risk: client compatibility. Effort: M.
3. Problem: PostgreSQL behavior is under-tested relative to SQLite/local tests. Why it matters: constraints, indexes, and locks differ. Proposed change: add PostgreSQL integration CI profile. Expected benefit: fewer production-only DB bugs. Risk: CI complexity. Effort: M.
4. Problem: Observability is not complete. Why it matters: incidents will take too long to diagnose. Proposed change: JSON logs, metrics endpoints, OpenTelemetry, baseline dashboards. Expected benefit: faster detection and recovery. Risk: tooling selection overhead. Effort: M.

### Medium Term (1-3 months)

1. Problem: Supabase API fallback can drift. Why it matters: business rules may behave differently by environment. Proposed change: either remove fallback for core mutations or generate shared contract tests for both paths. Expected benefit: deterministic behavior. Risk: losing emergency fallback. Effort: L.
2. Problem: Database growth plan is informal. Why it matters: audit/job tables and rollups will degrade. Proposed change: retention, partitioning/archive strategy, query-plan budgets, slow-query alerts. Expected benefit: stable performance. Risk: migration complexity. Effort: M-L.
3. Problem: Admin operations are ad hoc. Why it matters: incidents need safe repeatable commands. Proposed change: build admin CLI for user recovery, job retry/cancel, audit export, backup restore validation. Expected benefit: safer operations. Risk: CLI auth model needed. Effort: M.
4. Problem: Critical frontend journeys are thinly tested. Why it matters: UI regressions break core product value. Proposed change: Playwright suite for role-based Atlas journeys. Expected benefit: safer releases. Risk: flakiness. Effort: M.

### Long Term

1. Problem: Domain model and persistence are tightly coupled. Why it matters: future product changes will be expensive. Proposed change: introduce command/query application services and typed DTOs independent of ORM models. Expected benefit: clearer business rules and safer refactors. Risk: abstraction overreach. Effort: L.
2. Problem: Analytics and governance reads may outgrow transactional schemas. Why it matters: leadership dashboards can burden OLTP DB. Proposed change: introduce cached/materialized read models only where query plans prove need. Expected benefit: scalable reporting without microservices. Risk: cache invalidation complexity. Effort: L.
3. Problem: AI/PDF integrations may become operational cost centers. Why it matters: cost, latency, data egress, and provider failures affect reliability. Proposed change: per-team budgets, queued batch processing, retention controls, and provider circuit breakers. Expected benefit: predictable operations. Risk: product limitations. Effort: M-L.

## Top 10 Actions Before Scaling

1. Enforce distributed security state and private backend topology in every production path.
2. Add full-stack Docker Compose smoke tests to CI.
3. Add PostgreSQL-backed migration/authorization/RLS integration tests.
4. Generate route/auth/allowlist contract checks.
5. Standardize JSON logs, correlation IDs, and error envelopes.
6. Add dashboards and alerts for API, BFF, worker, DB, auth, and jobs.
7. Decompose `backend_app/main.py` and reduce `src/crud.py` facade responsibility.
8. Decide the future of Supabase API fallback and test/remove duplicate logic.
9. Define retention, partitioning, backup, and restore-drill policy.
10. Expand Playwright tests for critical role-based user journeys.

## If This Was My Company

First, I would make production failure modes observable and bounded: enforce distributed state, lock down backend ingress, add smoke tests, add route/auth/allowlist checks, and wire dashboards/alerts. These are disaster-prevention items.

Second, I would reduce the highest-change-risk modules without changing business behavior. The target is not a rewrite; it is moving route handlers and command logic into smaller domain-owned modules while preserving existing tests.

Third, I would make PostgreSQL the truth in CI for anything involving migrations, authorization, locking, indexes, and RLS. SQLite is useful for fast tests but is not enough for production confidence.

I would deliberately leave microservices, event sourcing, and a full frontend rewrite alone. The current modular-monolith-with-BFF shape is acceptable if boundaries are enforced, operational maturity improves, and duplicated fallback paths are controlled.
