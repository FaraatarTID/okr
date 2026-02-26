Documentation HQ: [README](../README.md)

Hybrid Frontend API Contract Inventory (Atlas Scope)

Date
- 2026-02-25

Purpose
- Provide a concrete contract map for SPA migration work.
- Define which backend endpoints and read-query kinds power Atlas-first flows.

Scope
- Covers Atlas core flows and adjacent dependencies used by authenticated workspace behavior.
- Excludes report rendering internals that remain Streamlit-native in early migration phases.

## Contract Matrix (Atlas Core)

| Operation | Backend Endpoint | Method | Contract Type | Query Kind (if `/v1/read/query`) | Notes |
| --- | --- | --- | --- | --- | --- |
| User login | `/v1/auth/login` | `POST` | `LoginRequest` | n/a | BFF forwards actor-independent login payload; backend returns serialized user snapshot. |
| Load active cycles | `/v1/read/query` | `POST` | `ReadQueryRequest` | `cycles.active` | Used for default cycle resolution in workspace bootstrap. |
| Load all cycles (admin/manage flows) | `/v1/read/query` | `POST` | `ReadQueryRequest` | `cycles.all` | Used by cycle management and admin views. |
| Load weekly focus plan | `/v1/read/query` | `POST` | `ReadQueryRequest` | `weekly_plan.active` | Supports top-level weekly focus card. |
| Load Atlas snapshot (primary map/read model) | `/v1/read/atlas/snapshot` | `POST` | `AtlasSnapshotRequest` | n/a | Preferred high-efficiency Atlas read path. |
| Read leadership aggregates | `/v1/read/leadership/metrics` | `POST` | `LeadershipMetricsRequest` | n/a | Supports dashboard-like strategic status reads. |
| Analyze KR/objective (AI) | `/v1/ai/analyze-node` | `POST` | `AiAnalyzeNodeRequest` | n/a | Semantic AI analysis path used by Inspector `Run Analysis`. |
| Generate team coach insights (AI) | `/v1/ai/team-coach` | `POST` | `AiTeamCoachRequest` | n/a | Semantic Team Coach path aligned with Streamlit `analyze_team_health`. |
| Generate strategy pulse insights (AI) | `/v1/ai/strategy-pulse` | `POST` | `AiStrategyPulseRequest` | n/a | Semantic Strategy Pulse path aligned with Streamlit burnout/gap/outlook workflow. |
| Resolve a node for inspector | `/v1/read/query` | `POST` | `ReadQueryRequest` | `node.get` | Canonical node read for inspector details. |
| Detect node type from id | `/v1/read/query` | `POST` | `ReadQueryRequest` | `node.detect_type` | Used in navigation/deep-link restoration paths. |
| Start timer | `/v1/timer/start` | `POST` | `TimerStartRequest` | n/a | Ownership/authorization enforced server-side. |
| Stop timer | `/v1/timer/stop` | `POST` | `TimerStopRequest` | n/a | Returns duration and summary fields for UX feedback. |
| Create goal | `/v1/nodes/goal` | `POST` | `GoalCreateRequest` | n/a | Mutation authority remains backend/domain-owned. |
| Create objective | `/v1/nodes/objective` | `POST` | `ObjectiveCreateRequest` | n/a | Goal-scoped authorization applies. |
| Create key result | `/v1/nodes/key_result` | `POST` | `KeyResultCreateRequest` | n/a | Goal-scoped authorization applies. |
| Create task | `/v1/nodes/task` | `POST` | `TaskCreateRequest` | n/a | Goal-scoped authorization applies. |
| Update node | `/v1/nodes/{node_type}/{node_id}` | `PATCH` | `NodeUpdateRequest` | n/a | Shared update path for Goal/Objective/KR/Task. |
| Delete node | `/v1/nodes/{node_type}/{node_id}` | `DELETE` | Path + actor header | n/a | Shared delete path for Goal/Objective/KR/Task. |
| Create check-in | `/v1/check-ins` | `POST` | `CheckInCreateRequest` | n/a | Key check-in update path for KR progress evidence. |
| Create/update/close experiments | `/v1/experiments` + `/v1/experiments/{id}` + `/v1/experiments/{id}/close` | `POST`/`PATCH`/`POST` | Experiment request schemas | n/a | Learning-loop flow attached to KR evidence. |
| Create retrospective | `/v1/retrospectives` | `POST` | `RetrospectiveCreateRequest` | n/a | Weekly reflection capture path. |
| Upsert retro experiment outcome | `/v1/retrospectives/{id}/experiment-outcomes` | `PUT` | `RetroExperimentOutcomeUpsertRequest` | n/a | Outcome closure link for retrospectives. |
| Create weekly plan | `/v1/weekly-plans` | `POST` | `WeeklyPlanCreateRequest` | n/a | Weekly planning path shown in workspace shell. |
| Create/delete alignment edge | `/v1/alignments` + `/v1/alignments/{edge_id}` | `POST`/`DELETE` | Alignment schemas | n/a | Objective alignment mutation flow. |
| Delete work log | `/v1/work-logs/{work_log_id}` | `DELETE` | Path + actor header | n/a | Supports timer/worklog cleanup flow. |

## Read Query Kind Coverage (Reference)

The following kinds are currently implemented in backend read-query dispatch and may be needed by SPA surfaces beyond Atlas core:
- `users.by_username`
- `users.by_id`
- `users.all`
- `users.team_members`
- `teams.all`
- `teams.by_id`
- `cycles.all`
- `cycles.active`
- `weekly_plan.active`
- `node.get`
- `node.detect_type`
- `krs.by_cycle`
- `tasks.by_cycle`
- `work_logs.by_range`
- `work_logs.by_task`
- `krs.needing_checkin`
- `experiments.active_for_kr`
- `experiments.for_retro_window`
- `retros.user`
- `retros.team`
- `alignments.context`
- `mindmap.root`

## Auth And Actor Contract

- `backend-api` endpoints are internal service-to-service endpoints, not browser-public contracts.
- BFF must attach:
  - `X-OKR-Service-Token`
  - `X-OKR-Signature`, `X-OKR-Timestamp`, `X-OKR-Nonce` when signing secret is configured/enforced
  - `X-OKR-Actor` for actor-scoped operations
- Authorization decisions remain in existing backend/domain logic.

### Actor Propagation Policy (Machine-Checked)

- For actor-scoped routes, `spa-bff` requires `X-OKR-Actor` and rejects missing actor headers (`400`).
- `POST /v1/auth/login` is the only allowlisted route that does not require actor header forwarding.
- Backend actor resolution precedence is explicit:
  1. `X-OKR-Actor` header (canonical)
  2. payload actor field fallback (`actor_username`/`user_id`) if header is absent
- Unauthorized actors are rejected by backend authorization scope checks (`403`).

Validation coverage:
- BFF actor guard and forwarding tests: `spa-bff/test/server.test.ts`, `spa-bff/test/allowlist.test.ts`
- Backend actor precedence and unauthorized-path tests: `tests/test_backend_mutation_api.py`
- Timer mutation parity tests (authorization + status outcomes): `tests/test_backend_mutation_api.py`, `spa-bff/test/server.test.ts`
- Node mutation parity tests (Goal/Objective/KR/Task create/update/delete contract + proxy passthrough): `tests/test_backend_mutation_api.py`, `tests/test_hybrid_frontend_contract_fixtures.py`, `spa-bff/test/server.test.ts`, `spa-bff/test/allowlist.test.ts`
- AI analysis/team-coach parity tests (actor precedence + status mapping + proxy passthrough): `tests/test_backend_mutation_api.py`, `spa-bff/test/server.test.ts`, `spa-bff/test/allowlist.test.ts`
- AI strategy-pulse parity tests (actor scope + user resolution + status mapping + proxy passthrough): `tests/test_backend_mutation_api.py`, `spa-bff/test/server.test.ts`, `spa-bff/test/allowlist.test.ts`

## SPA Rollout Cohort Policy

- `spa-web` exposes runtime rollout policy via `GET /api/rollout` (Next.js server route, not backend-api).
- Policy is driven by environment variables:
  - `OKR_SPA_ROLLOUT_ENABLED`
  - `OKR_SPA_ROLLOUT_ALLOW_ALL`
  - `OKR_SPA_ROLLOUT_TEAM_IDS`
  - `OKR_SPA_ROLLOUT_USERNAMES`
  - `OKR_SPA_ROLLOUT_ROLES`
  - `OKR_SPA_ROLLOUT_ALLOW_PREVIEW_BYPASS`
- Cohort evaluation runs client-side after login using backend-returned actor profile (`username`, `role`, `team_id`).

## Unified SPA Runtime Contract

- Core report, dashboard, check-in, admin, timeline, and Atlas workflows run directly inside SPA routes.
- No Streamlit bridge route is required for core operation.

## Allowlist Alignment

Current BFF allowlist implementation for these routes lives in:
- `spa-bff/src/allowlist.ts`

The allowlist is intentionally strict:
- unknown routes are denied by default (`403`).
- only Atlas-core and governance-critical routes are currently included.

### Allowlist Signatures (Machine-Checked)

```text
DELETE /v1/alignments/{edge_id:int}
DELETE /v1/cycles/{cycle_id:int}
DELETE /v1/jobs/{job_id}
DELETE /v1/nodes/{node_type}/{node_id:int}
DELETE /v1/teams/{team_id:int}
DELETE /v1/work-logs/{work_log_id:int}
GET /v1/admin/ai-health
GET /v1/admin/db-backup
GET /v1/admin/pdf-health
GET /v1/jobs/{job_id}
PATCH /v1/experiments/{experiment_id:int}
PATCH /v1/nodes/{node_type}/{node_id:int}
PATCH /v1/teams/{team_id:int}
PATCH /v1/users/{user_id:int}
PATCH /v1/cycles/{cycle_id:int}
POST /v1/admin/db-restore
POST /v1/ai/analyze-node
POST /v1/ai/strategy-pulse
POST /v1/ai/team-coach
POST /v1/alignments
POST /v1/auth/login
POST /v1/check-ins
POST /v1/experiments
POST /v1/experiments/{experiment_id:int}/close
POST /v1/jobs
POST /v1/jobs/{job_id}/cancel
POST /v1/nodes/{create_type}
POST /v1/read/atlas/snapshot
POST /v1/read/leadership/metrics
POST /v1/read/query
POST /v1/retrospectives
POST /v1/teams
POST /v1/timer/start
POST /v1/timer/stop
POST /v1/users
POST /v1/users/{user_id:int}/reset-password
POST /v1/weekly-plans
POST /v1/cycles
PUT /v1/retrospectives/{retrospective_id:int}/experiment-outcomes
```

## Golden Contract Fixtures (Machine-Checked)

Critical request/response fixtures live in:
- `docs/fixtures/hybrid_frontend/manifest.json`

Fixture set:
- `docs/fixtures/hybrid_frontend/auth_login.request.json`
- `docs/fixtures/hybrid_frontend/auth_login.response.json`
- `docs/fixtures/hybrid_frontend/atlas_snapshot.request.json`
- `docs/fixtures/hybrid_frontend/atlas_snapshot.response.json`
- `docs/fixtures/hybrid_frontend/timer_start.request.json`
- `docs/fixtures/hybrid_frontend/timer_start.response.json`
- `docs/fixtures/hybrid_frontend/timer_stop.request.json`
- `docs/fixtures/hybrid_frontend/timer_stop.response.json`
- `docs/fixtures/hybrid_frontend/node_create.request.json`
- `docs/fixtures/hybrid_frontend/node_create.response.json`
- `docs/fixtures/hybrid_frontend/node_delete.request.json`
- `docs/fixtures/hybrid_frontend/node_delete.response.json`
- `docs/fixtures/hybrid_frontend/node_update.request.json`
- `docs/fixtures/hybrid_frontend/node_update.response.json`

CI guards:
- `tests/test_hybrid_frontend_contract_fixtures.py` validates backend schema compatibility and response shape invariants.
- `spa-bff/test/critical-fixtures.test.ts` validates all critical fixture endpoints remain BFF-allowlisted.

## Open Items

1. Define versioning strategy for BFF public routes before exposing SPA to wider cohorts.

