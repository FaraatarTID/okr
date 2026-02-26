# Hybrid Frontend Migration Plan (Repo Accurate)

Documentation HQ: [README](../README.md)

Last updated: 2026-02-25

Companion execution docs
- Backlog: [HYBRID_FRONTEND_MIGRATION_BACKLOG.md](HYBRID_FRONTEND_MIGRATION_BACKLOG.md)
- Phase 0 checklist: [HYBRID_FRONTEND_PHASE0_CHECKLIST.md](HYBRID_FRONTEND_PHASE0_CHECKLIST.md)
- API contract inventory: [HYBRID_FRONTEND_API_CONTRACT_INVENTORY.md](HYBRID_FRONTEND_API_CONTRACT_INVENTORY.md)
- Cohort rollout playbook: [HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md](HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md)
- Iframe feasibility decision: [HYBRID_FRONTEND_IFRAME_FEASIBILITY.md](HYBRID_FRONTEND_IFRAME_FEASIBILITY.md)
- SLO dashboard and thresholds: [HYBRID_FRONTEND_SLO_DASHBOARD.md](HYBRID_FRONTEND_SLO_DASHBOARD.md), [HYBRID_FRONTEND_SLO_TARGETS.json](HYBRID_FRONTEND_SLO_TARGETS.json)
- Rollback drill evidence: [HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md](HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md), [HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.json](HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.json)
- Pilot completion review: [HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.md](HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.md), [HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.json](HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.json)
- SPA shell validation evidence: [HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.md](HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.md), [HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.json](HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.json)
- Read parity validation evidence: [HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.md](HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.md), [HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.json](HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.json)
- Phase 0 baseline snapshot: [HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.md](HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.md), [HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.json](HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.json)
- Rollback toggle contract: [HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.md](HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.md), [HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.json](HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.json)

## Executive Summary

This is a replacement for the original React/Vue hybrid plan. It keeps what is strong (phased rollout, Atlas-first migration, Streamlit analytics reuse) and corrects key architecture mismatches with the current repository.

Primary correction:
- Do not let a browser SPA call `backend-api` directly.
- In this repo, backend APIs are internal service-to-service contracts protected by shared token and request signing.
- Introduce a public-facing BFF layer for SPA traffic, and keep `backend-api` internal.

## Why The Original Plan Needed Changes

1. `backend-api` is internal by design.
- Compose binds it to loopback by default (`127.0.0.1`).
- Security policy expects internal callers only.

2. Backend auth model is service-auth, not browser-auth.
- Calls require `OKR_BACKEND_SERVICE_TOKEN`.
- Signed requests are expected with `OKR_BACKEND_SIGNING_SECRET` when enabled.

3. Sidebar scope is broader than "reports only".
- Current sidebar includes Weekly, Daily, Check-In, RetroBox, Timeline, Dashboard, and Admin flows.

4. Report navigation is mode-based, not route-per-report today.
- Existing state/query model uses mode keys (for example `mode=Weekly`, `mode=Daily`).

## Target End-State Architecture

- Public ingress:
  - `spa-web` (new)
  - `streamlit-app` (existing, retained during migration)
  - `spa-bff` (new public API for browser clients)
- Internal only:
  - `backend-api` (existing FastAPI internal control plane)
  - `backend-worker` (existing async worker)
  - PostgreSQL

Request flow for SPA:
- Browser -> `spa-web` -> `spa-bff` -> `backend-api` -> DB

Request flow for legacy Streamlit:
- Browser -> `streamlit-app` -> `backend-api` -> DB

## Phase 0: Baseline Lock And Release Guardrails

Goal:
- Freeze current behavior and establish no-regression gates before migration work.

Work:
1. Run and record baseline checks:
- `python -m pytest -q`
- Playwright happy-path login to Atlas timer flow.
- Runtime deploy policy gate (`scripts/check_deploy_config.py --mode runtime ...`).
2. Confirm production hardening defaults are enforced in runtime env:
- `OKR_BACKEND_PROXY_MUTATIONS=true`
- `OKR_BACKEND_PROXY_READS=true`
- `OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true`
- `ALLOW_EXTERNAL_AI=false` unless explicitly approved.
3. Define rollback rule:
- Legacy Streamlit UI remains the immediate fallback path for all pilot teams.

Go/No-Go:
- Go only if baseline tests pass and runtime config gate is clean.

## Phase 1: Contract Inventory And API Fit

Goal:
- Build a complete list of Atlas operations required by SPA and map them to stable backend contracts.

Work:
1. Inventory Atlas operation set:
- Focus Map read/scope navigation
- Focus Task timer start/stop
- Inspector read/update/create/delete paths
- Cycle selector and role-aware scope reads
2. Document endpoint mapping and payload schemas.
3. Add contract tests (or snapshot checks) for payload compatibility on critical endpoints.
4. Capture auth/actor propagation contract:
- Every call must include actor context.
- Authorization remains enforced in existing backend/domain layers.

Go/No-Go:
- Go only when all required Atlas actions have mapped endpoints and passing contract checks.

## Phase 2: Introduce `spa-bff` (Mandatory Security Layer)

Goal:
- Enable browser traffic without exposing internal service credentials.

Work:
1. Create `spa-bff` service with strict route allowlist.
2. Keep `OKR_BACKEND_SERVICE_TOKEN` and signing secret only in BFF/server environment.
3. BFF responsibilities:
- User session handling for SPA clients.
- Actor resolution and forwarding to backend.
- Request signing and backend token auth.
- Rate limiting and audit correlation ids.
4. Keep `backend-api` private (no public ingress route).
5. Add security tests:
- Reject unsigned/unauthorized direct backend calls.
- Verify secrets are never present in browser bundles.

Go/No-Go:
- Go only if SPA can complete Atlas read/write via BFF and direct browser access to backend remains blocked.

## Phase 3: SPA Shell With Atlas Read-Only Parity

Goal:
- Deliver user-visible SPA speed improvements with low risk by starting read-only.

Work:
1. Implement SPA shell:
- Navigation
- Cycle selector
- Scope selector
- Atlas map and inspector read surfaces
2. Preserve deep-link semantics where feasible (`cycle`, `mode`, `sel`, `ft`, `lens`).
3. Add feature flag for pilot rollout:
- Example: `OKR_EXPERIMENTAL_SPA=true` per environment/team.
4. Keep Streamlit as default write UI until Phase 4.

Go/No-Go:
- Go only when read parity is validated by pilot users and no authorization regressions are found.

## Phase 4: Atlas Write Paths In SPA

Goal:
- Migrate daily execution workflows (highest UX pain) to SPA.

Work:
1. Implement in SPA via BFF:
- Timer start/stop
- Inspector updates
- Goal/Objective/KR/Task create/update/delete paths needed for pilot scope
2. Keep RBAC/authorization server-side only.
3. Add parity tests against legacy Streamlit outcomes:
- Same mutation result
- Same authorization failures
- Same audit/event behavior
4. Gradual rollout by team cohort.

Go/No-Go:
- Go only when timer and inspector paths reach parity and incident rate is within agreed threshold.

## Phase 5: Streamlit Analytics Integration

Goal:
- Reuse existing analytics/reporting without immediate rewrite.

Work:
1. Integrate report access from SPA navigation using one of two patterns:
- Preferred initial: route users to Streamlit report modes through proxied paths (lowest coupling).
- Optional later: iframe embedding only after CSP/X-Frame-Options validation and session model validation.
2. Preserve role/authorization behavior and existing report exports.
3. Track usage to decide what to reimplement natively later.

Go/No-Go:
- Go only when report access from SPA nav is reliable and support burden is acceptable.

## Phase 6: Cutover, SLOs, And Rollback

Goal:
- Production cutover with fast rollback path.

Work:
1. Progressive rollout:
- Wave 1: 1-2 teams
- Wave 2: 25-50% of pilot scope
- Wave 3: default for all pilot teams
2. SLOs and alerts:
- Login success rate
- Timer mutation success/latency
- Atlas read latency
- Report open success rate
3. Rollback:
- One toggle to return affected cohorts to Streamlit-first UI immediately.

Go/No-Go:
- Full cutover only after two stable reporting periods (for example, two weekly cycles) at target SLO.

## Non-Goals For This Migration

- Replacing backend domain/authorization logic.
- Exposing `backend-api` publicly.
- Full Streamlit report reimplementation in SPA in first pass.
- Immediate SSO rewrite unless separately approved and scoped.

## Suggested Timeline (Realistic Range)

- Phase 0-2: 3-5 weeks
- Phase 3-4: 4-8 weeks
- Phase 5-6: 2-4 weeks

Total: 9-17 weeks, depending on team size and required parity depth.

## Exit Criteria (Program-Level)

1. Security:
- No internal service secrets in browser surface.
- Backend remains private/internal.
2. Functional parity:
- Atlas core read/write parity for pilot scope.
3. Reliability:
- Error rate and latency at or better than legacy baseline.
4. Operational readiness:
- On-call runbook updated.
- Rollback tested in staging and once in production-safe drill.

