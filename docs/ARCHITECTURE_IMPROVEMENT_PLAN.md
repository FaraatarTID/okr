Documentation HQ: [README](../README.md)

Architecture Improvement Plan (From External Review)

Purpose
- Convert valid external review points into an actionable implementation roadmap.
- Improve security boundaries, runtime scalability, and operational reliability without destabilizing current delivery.
- Build on existing controls already present in this repository (backend-assisted writes, request signing support, performance budgets/tests).

Context Snapshot (Current State)
- Writes: backend-assisted mode routes frontend mutations through `backend-api`.
- Reads: major hierarchy reads are still in-process from Streamlit to DB.
- Async heavy work: `async_job` table + `backend-worker` polling loop.
- Security baseline: service token + optional request signing + runtime preflight checks.
- Performance baseline: Atlas snapshot caching and query-budget tests are already in place.

Guiding Principles
- Fail closed in production for all mutation and security-critical paths.
- Keep one mutation authority (`backend-api`) and gradually move read APIs behind backend contracts.
- Prefer measurable guardrails (tests, budgets, SLOs) over one-time fixes.
- Preserve MVP velocity by sequencing high-risk changes first, then progressive decoupling.

Phase Plan

Phase 0: Baseline and Guardrails (Week 1)
Owner: Platform + Backend + QA
Goals
- Establish objective baselines before major refactors.
Tasks
- Freeze baseline metrics:
  - Atlas read path latency (median/p95), query counts, payload sizes.
  - Async job queue depth, age, success/failure/cancel rates.
  - DB connection counts and CPU under normal traffic.
- Add dashboard KPIs for:
  - `async_job` pending/running depth and max age.
  - Backend mutation error rate by status code.
  - Streamlit cache hit ratio on Atlas snapshot/runtime helpers.
- Add release gate checks:
  - `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false` and `OKR_ALLOW_LOCAL_READ_FALLBACK=false` in production.
  - backend token/signing config present in production.
Acceptance Criteria
- Baseline report stored and referenced from operations docs.
- Alerts defined for queue backlog and backend mutation failures.

Phase 1: Security Boundary Tightening (Weeks 1-2)
Owner: Backend + Security
Goals
- Close remaining least-privilege and split-boundary gaps.
Tasks
- Keep `backend-api` as sole production mutation authority (already mostly implemented); audit and remove any remaining production-direct mutation bypasses.
- Move admin backup/restore out of direct Streamlit DB operation path:
  - Option A: backend-admin endpoints with strict admin auth and audit.
  - Option B: operator-only runbook command (preferred for destructive restore).
- Enforce production runtime invariants:
  - service token required.
  - request signing required.
  - local fallback disabled.
- Ensure backend private-network exposure remains default in all deploy modes.
Acceptance Criteria
- No production UI route performs direct DB destructive admin operation.
- Mutation attempts without backend auth/signing fail with deterministic 401/403.
- Deployment checklist includes explicit verification steps and evidence.

Phase 2: Async Queue Hardening (Weeks 2-3)
Owner: Backend + Platform
Goals
- Keep DB-backed queue viable under sustained load.
Tasks
- Add retention/pruning workflow for `async_job`:
  - Delete or archive terminal jobs (`succeeded/failed/cancelled`) older than retention threshold.
  - Keep minimal audit metadata if full payload retention is not required.
- Add queue maintenance controls:
  - max pending jobs per actor/team (already partially implemented; validate in load tests).
  - backlog age alerts and auto-remediation playbook.
- Validate indexes remain aligned with hot queue queries (`status`, `created_at`, ownership dimensions).
- Document retention policy and operational ownership.
Acceptance Criteria
- Queue table growth remains bounded in soak tests.
- No backlog growth without alert firing.
- Runbook includes prune schedule, retention days, and rollback steps.

Phase 3: Read Path API Decoupling (Weeks 3-5)
Owner: Backend + Streamlit
Goals
- Reduce split-brain architecture by moving highest-impact reads to backend.
Tasks
- Introduce versioned read endpoints for the hottest paths first:
  - Atlas hierarchy snapshot.
  - leadership metrics.
  - cycle-wide KR/task summaries.
- Keep query shaping in backend (set-based queries, no lazy graph traversal).
- Update Streamlit to consume backend read contracts behind feature flags.
- Add contract tests for payload shape and backward compatibility.
Acceptance Criteria
- At least two top read-heavy paths served by backend endpoints in production profile.
- Query budgets for migrated paths are preserved or improved.
- Streamlit read code can be switched between local/backend path via controlled flag during rollout.

Phase 4: Performance and Scale Validation (Weeks 5-6)
Owner: QA + Platform + Backend
Goals
- Demonstrate improved behavior under realistic concurrency.
Tasks
- Extend perf suite to include:
  - concurrent Atlas navigation.
  - concurrent timer start/stop.
  - mixed read + async job submission load.
- Validate DB and app behavior under worker polling and API traffic together.
- Tune cache TTL/key strategy based on measured staleness and hit rate.
- Add regression thresholds to CI/nightly for critical budgets.
Acceptance Criteria
- Documented pass on agreed SLO thresholds (latency, error rate, queue age).
- No new N+1 regressions in critical path tests.

Phase 5: Deployment Parity and Documentation (Week 6)
Owner: Platform + Docs
Goals
- Ensure architecture is consistently deployable across Compose and Kubernetes.
Tasks
- Add/maintain Kubernetes manifests for `backend-api` and `backend-worker` (currently Streamlit-focused).
- Update docs to reflect final mutation/read routing and operational responsibilities.
- Publish final architecture decision record (ADR) for:
  - mutation authority,
  - read API strategy,
  - queue retention policy.
Acceptance Criteria
- Compose and Kubernetes both deploy full backend-assisted topology.
- Docs and checklists match actual runtime topology and security posture.

Priority Backlog (Ranked)
P0
- Remove production direct DB restore path from Streamlit UI.
- Implement `async_job` retention/pruning.
- Complete production invariant checks in runtime/deploy gates.

P1
- Migrate Atlas snapshot read to backend endpoint.
- Add queue/latency observability dashboard + alerts.
- Add backend-read contract tests.

P2
- Migrate remaining heavy read paths.
- Expand nightly load/perf regression automation.

Risks and Mitigations
- Risk: migration churn breaks current UI workflows.
  - Mitigation: feature flags + canary rollout + contract tests.
- Risk: queue pruning deletes data needed for incident analysis.
  - Mitigation: dual-mode retention (archive summary + prune payload) and configurable retention windows.
- Risk: backend read API introduces payload/latency overhead.
  - Mitigation: endpoint-level budgets and structured snapshot payloads.

Success Metrics
- Security
  - 0 production mutations outside backend authority.
  - 0 successful unsigned/replayed internal requests.
- Reliability
  - async queue max age stays below threshold in normal operation.
  - worker failure ratio within defined error budget.
- Performance
  - Atlas read path median/p95 at or better than current baseline.
  - no query-budget regressions in `tests/test_atlas_cache_performance.py` and related suites.

Definition of Done
- Production architecture enforces backend-only mutations and hardened internal auth.
- Queue lifecycle includes retention, pruning, and alerting.
- At least the highest-impact read paths are backend-served with stable contracts.
- Compose/Kubernetes docs and manifests reflect the same full topology.
