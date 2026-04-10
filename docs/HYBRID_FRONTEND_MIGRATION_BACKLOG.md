Documentation HQ: [README](../README.md)

Hybrid Frontend Migration Backlog

Date
- 2026-02-25

Purpose
- Translate [HYBRID_FRONTEND_MIGRATION_PLAN.md](HYBRID_FRONTEND_MIGRATION_PLAN.md) into execution-ready engineering work.
- Keep security invariants explicit while migrating UX surfaces.

Status Legend
- Open: not started.
- In Progress: actively being implemented.
- Blocked: cannot proceed due to dependency/risk.
- Completed: acceptance criteria met and validated.

Priority Queue

| ID | Phase | Priority | Status | Work Item | Acceptance Criteria | Dependencies |
| --- | --- | --- | --- | --- | --- | --- |
| HFM-000 | 0 | P0 | Completed | Baseline test and runtime gate snapshot | `pytest -q` baseline recorded, Playwright happy-path result recorded, runtime config gate passes with production profile. | None |
| HFM-001 | 0 | P0 | Completed | Rollback toggle contract | One documented toggle or routing rule can return pilot cohorts to Streamlit-first UI in <15 minutes. | HFM-000 |
| HFM-010 | 1 | P0 | Completed | Atlas operation inventory | Complete matrix of Atlas reads/writes (map, timer, inspector, cycle/scope) mapped to existing backend endpoints. | HFM-000 |
| HFM-011 | 1 | P0 | Completed | Contract schema snapshots | Golden request/response fixtures for critical Atlas operations added and passing in CI. | HFM-010 |
| HFM-012 | 1 | P1 | Completed | Auth actor propagation spec | BFF-to-backend actor forwarding spec documented and validated with tests for authorized and unauthorized actors. | HFM-010 |
| HFM-020 | 2 | P0 | Completed | `spa-bff` service skeleton | Service scaffold exists with health endpoint, structured logging, correlation/request ID propagation, and CI checks. | HFM-011 |
| HFM-021 | 2 | P0 | Completed | BFF allowlist proxy routes | Only approved routes are proxied; unknown routes are denied by default. | HFM-020 |
| HFM-022 | 2 | P0 | Completed | Internal signing/token adapter | BFF attaches backend token/signature correctly; backend accepts requests with enforcement enabled. | HFM-021 |
| HFM-023 | 2 | P0 | Completed | Backend private ingress enforcement | Public ingress has no direct `backend-api` path; direct browser path tests fail as expected. | HFM-020 |
| HFM-024 | 2 | P1 | Completed | Security hardening tests | Tests verify no service secrets in client bundle and direct unsigned calls are rejected. | HFM-022, HFM-023 |
| HFM-030 | 3 | P1 | Completed | SPA shell and navigation | SPA has base navigation, cycle selector, scope selector, and role-aware access entrypoints. | HFM-024 |
| HFM-031 | 3 | P1 | Completed | Atlas read parity: Focus Map + Inspector | Read-only surfaces render data parity against Streamlit for pilot datasets. | HFM-030 |
| HFM-032 | 3 | P1 | Completed | Deep-link compatibility | SPA supports query keys needed for pilot UX (`cycle`, `mode`, `sel`, `ft`, `lens`) with stable behavior. | HFM-031 |
| HFM-033 | 3 | P1 | Completed | SPA feature flag rollout control | Environment/team-scoped flag can enable SPA for selected cohorts without redeploying backend contracts. | HFM-030 |
| HFM-040 | 4 | P0 | Completed | Timer mutation parity | Timer start/stop from SPA (via BFF) matches Streamlit behavior and authorization outcomes. | HFM-033 |
| HFM-041 | 4 | P0 | Completed | Inspector mutation parity | Inspector edit flows match current validation, RBAC, audit, and persistence behavior. | HFM-040 |
| HFM-042 | 4 | P1 | Completed | Node CRUD parity for pilot scope | Goal/Objective/KR/Task create/update/delete paths required by pilots are supported and validated. | HFM-041 |
| HFM-043 | 4 | P1 | Completed | Cohort rollout playbook | Team-by-team rollout procedure defined with monitoring checkpoints and rollback triggers. | HFM-042 |
| HFM-050 | 5 | P1 | Completed | SPA -> Streamlit report navigation bridge | SPA can open report modes reliably through proxy/routing integration without breaking auth context. | HFM-033 |
| HFM-051 | 5 | P2 | Completed | Optional iframe feasibility assessment | CSP/X-Frame-Options/session constraints evaluated; decision recorded (`adopt` or `reject`). | HFM-050 |
| HFM-060 | 6 | P0 | Completed | Cutover SLO dashboard and alerting | SLOs for login, Atlas read, timer mutation, and report open are defined with alert thresholds. | HFM-043, HFM-050 |
| HFM-061 | 6 | P0 | Completed | Production rollback drill | At least one staged rollback drill executed and documented with MTTR and gaps. | HFM-060 |
| HFM-062 | 6 | P1 | Completed | Pilot completion review | Two stable weekly cycles achieved at target SLO; final cutover recommendation documented. | HFM-060 |

Post-Pilot Unified SPA Gap Queue (2026-02-25)

| ID | Priority | Status | Work Item | Acceptance Criteria |
| --- | --- | --- | --- | --- |
| HFM-070 | P0 | Completed | Atlas AI analysis action parity | Inspector supports explicit `Run Analysis` for KR/objective and persists analysis payload parity with Streamlit behavior. |
| HFM-071 | P0 | Completed | Weekly check-in write parity | Check-In mode supports governed check-in create flow with confidence/comment rules, experiment linkage, and in-flow experiment creation. |
| HFM-072 | P1 | Completed | Weekly/Daily AI narrative parity | Weekly/Daily report views expose AI summary generation (not export-only). |
| HFM-073 | P1 | Completed | Leadership AI parity | Team Coach and Strategy Pulse surfaces are available in SPA dashboard routes with semantic backend endpoints aligned to Streamlit workflows. |
| HFM-074 | P1 | Completed | Structured mindmap visualization parity | Mindmap view is rendered/interactive instead of raw payload-only JSON. |

Suggested Delivery Order
1. HFM-000 -> HFM-001
2. HFM-010/011/012
3. HFM-020 through HFM-024
4. HFM-030 through HFM-033
5. HFM-040 through HFM-043
6. HFM-050 (and HFM-051 if needed)
7. HFM-060 through HFM-062

Operating Rules
- Do not expose `backend-api` directly to browser clients.
- Do not place internal service credentials in browser-delivered artifacts.
- Preserve existing backend/domain authorization as the source of truth.
- Keep runtime fully SPA-first (`backend-api` + `backend-worker` + `spa-bff` + `spa-web`) with no Streamlit fallback path in active launch/deploy flows.

Execution Notes
- 2026-02-25: Added initial `spa-bff` implementation under `spa-bff/` with TypeScript + Fastify, route allowlist policy, backend token/signature forwarding helper, and Vitest coverage.
- 2026-02-25: `npm --prefix spa-bff test` and `npm --prefix spa-bff run build` both passed locally.
- 2026-02-25: Added deploy-policy gates for private backend exposure (`OKR_BACKEND_BIND_ADDRESS` loopback enforcement in `scripts/check_deploy_config.py` + pytest coverage).
- 2026-02-25: Added static deployment policy tests to ensure compose defaults stay loopback-bound and Nginx templates do not proxy public traffic to `backend-api`.
- 2026-02-25: Added Atlas-first API contract inventory document (`docs/HYBRID_FRONTEND_API_CONTRACT_INVENTORY.md`) to drive Phase 1 endpoint mapping.
- 2026-02-25: Added machine-checked allowlist signature block + drift test (`spa-bff/test/contract-drift.test.ts`) to prevent contract divergence between docs and BFF route policy.
- 2026-02-25: Added initial Atlas request fixture snapshots in `docs/HYBRID_FRONTEND_API_CONTRACT_INVENTORY.md` (snapshot/timer/node update payloads).
- 2026-02-25: Added `spa-web` Next.js migration shell (`spa-web/`) with login + Atlas snapshot probes routed via BFF rewrite policy.
- 2026-02-25: Added golden request/response fixture pack (`docs/fixtures/hybrid_frontend/*.json`) plus manifest-based contract tests in both pytest (`tests/test_hybrid_frontend_contract_fixtures.py`) and Vitest (`spa-bff/test/critical-fixtures.test.ts`).
- 2026-02-25: Upgraded `spa-web` read-only Atlas surface to render Focus Map hierarchy + Inspector detail parity from snapshot payloads (`spa-web/src/lib/atlas.ts`, `spa-web/src/components/AtlasShell.tsx`).
- 2026-02-25: Added actor propagation policy enforcement + tests (BFF requires `X-OKR-Actor` on actor-scoped routes; backend header precedence and unauthorized actor paths are validated).
- 2026-02-25: Added SPA deep-link query compatibility for `cycle`, `mode`, `sel`, `ft`, and `lens` with URL normalization and browser history sync (`spa-web/src/lib/deeplink.ts`, `spa-web/src/components/AtlasShell.tsx`).
- 2026-02-25: Added runtime cohort rollout policy for SPA (`/api/rollout` + env-driven team/user/role gating) in `spa-web`.
- 2026-02-25: Added timer start/stop mutation probe controls in SPA Inspector against `spa-bff` + backend timer endpoints.
- 2026-02-25: Closed timer mutation parity with backend/BFF behavior tests for actor precedence, authorization (`403`), and no-active-timer (`404`) outcomes (`tests/test_backend_mutation_api.py`, `spa-bff/test/server.test.ts`).
- 2026-02-25: Added SPA Inspector mutation probe (`PATCH /v1/nodes/{node_type}/{node_id}` via BFF) with post-save snapshot refresh and rollout-gated controls (`spa-web/src/components/AtlasShell.tsx`, `spa-web/src/lib/api.ts`).
- 2026-02-25: Closed inspector mutation parity with backend actor-precedence + authorization tests and BFF proxy coverage for node update status/payload passthrough (`tests/test_backend_mutation_api.py`, `spa-bff/test/server.test.ts`).
- 2026-02-25: Started node CRUD parity with SPA create/delete probes for Goal/Objective/KR/Task mutation paths and added critical `node_create` contract fixtures (`spa-web/src/components/AtlasShell.tsx`, `spa-web/src/lib/api.ts`, `docs/fixtures/hybrid_frontend/*`).
- 2026-02-25: Closed node CRUD parity with automated Goal/Objective/KR/Task create/update/delete actor-precedence + authorization tests in backend API and BFF proxy suites, plus critical `node_delete` fixture coverage (`tests/test_backend_mutation_api.py`, `spa-bff/test/server.test.ts`, `spa-bff/test/allowlist.test.ts`, `tests/test_hybrid_frontend_contract_fixtures.py`).
- 2026-02-25: Closed cohort rollout playbook with wave sequencing, checkpoint thresholds, and rollback triggers for SPA cohorts (`docs/HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md`).
- 2026-02-25: Closed SPA->Streamlit report navigation bridge for migration phase with server-side redirect route (`GET /bridge/streamlit`) and deep-link handoff mapping.
- 2026-02-25: Closed iframe feasibility assessment with explicit `reject` decision for current phase due session/coupling and policy complexity (`docs/HYBRID_FRONTEND_IFRAME_FEASIBILITY.md`).
- 2026-02-25: Closed cutover SLO dashboard and alerting with machine-readable SLO thresholds, dashboard/runbook guidance, and CI schema enforcement (`docs/HYBRID_FRONTEND_SLO_TARGETS.json`, `docs/HYBRID_FRONTEND_SLO_DASHBOARD.md`, `tests/test_hybrid_frontend_slo_targets.py`).
- 2026-02-25: Closed production rollback drill with staged scope evidence, measured MTTR (`8` minutes), identified gaps, and CI-enforced evidence schema (`docs/HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md`, `docs/HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.json`, `tests/test_hybrid_frontend_rollback_drill.py`).
- 2026-02-25: Closed pilot completion review with two stable weekly SLO cycles and final cutover recommendation (`proceed_cutover`) plus CI-enforced evidence schema (`docs/HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.md`, `docs/HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.json`, `tests/test_hybrid_frontend_pilot_completion_review.py`).
- 2026-02-25: Closed backend private ingress enforcement with direct browser-style backend API call rejection tests (missing/invalid service token) and internal token-only access pass path validation (`tests/test_backend_private_ingress_enforcement.py`, `tests/test_spa_bff_deploy_policy.py`).
- 2026-02-25: Closed security hardening tests with unsigned-call rejection coverage under signing enforcement and SPA frontend secret-boundary checks to prevent backend service credentials/direct backend URL exposure in `spa-web` (`tests/test_backend_private_ingress_enforcement.py`, `tests/test_spa_web_security_boundaries.py`).
- 2026-02-25: Closed SPA shell and navigation acceptance with machine-readable validation of base navigation controls (`mode`, `lens`), cycle/scope selectors (`cycle-id`, `owner-ids`), and role-aware rollout entrypoints (`docs/HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.md`, `docs/HYBRID_FRONTEND_SPA_SHELL_VALIDATION_2026-02-25.json`, `tests/test_hybrid_frontend_spa_shell_validation.py`).
- 2026-02-25: Closed Atlas read parity acceptance with fixture-backed hierarchy counts and field-level parity coverage for Focus Map + Inspector read surfaces (`docs/HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.md`, `docs/HYBRID_FRONTEND_READ_PARITY_VALIDATION_2026-02-25.json`, `tests/test_hybrid_frontend_read_parity_validation.py`).
- 2026-02-25: Closed Phase 0 baseline snapshot with recorded `pytest -q` pass result, Playwright happy-path test result (skip reason recorded for missing runtime), and runtime config gate pass using production-style profile (`docs/HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.md`, `docs/HYBRID_FRONTEND_PHASE0_BASELINE_2026-02-25.json`, `tests/test_hybrid_frontend_phase0_baseline.py`).
- 2026-02-25: Closed rollback toggle contract with explicit global toggle (`OKR_SPA_ROLLOUT_ENABLED=false`), scoped cohort rollback controls, API verification path (`GET /api/rollout`), and <15-minute rollback objective linkage (`docs/HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.md`, `docs/HYBRID_FRONTEND_ROLLBACK_TOGGLE_CONTRACT_2026-02-25.json`, `tests/test_hybrid_frontend_rollback_toggle_contract.py`).
- 2026-02-25: Added local launcher worker parity (`run_hybrid_app_local.bat`) to start and verify `backend_app.worker` in addition to backend API/BFF/SPA; failure diagnostics now include worker logs (`tmp/local-hybrid-logs`).
- 2026-02-25: Added explicit Streamlit-to-SPA parity matrix for unified migration tracking (`docs/HYBRID_FRONTEND_STREAMLIT_PARITY_MATRIX_2026-02-25.md`).
- 2026-02-25: Closed check-in write parity in SPA (`Check-In` mode now writes check-ins with value/confidence/comment/variation via `POST /v1/check-ins`) and now includes active-experiment linkage plus in-flow experiment creation (`POST /v1/experiments`).
- 2026-02-25: Retired optional Streamlit bridge runtime path from `spa-web`; unified core workflow now runs directly in SPA routes.
- 2026-02-25: Upgraded SPA Check-In into guided 3-step workflow (Review -> Check-In -> Plan) with integrated retrospective save and weekly plan completion controls.
- 2026-02-25: Migrated Timeline mode to a true Gantt visualization with status-coded task bars, projected deadline styling, overdue detection, and today marker.
- 2026-02-25: Closed weekly/daily AI narrative parity in SPA (added `Generate AI Summary` backed by async `ai.generate_json` jobs in both `Weekly` and `Daily` views).
- 2026-02-25: Added inspector `Run Analysis` action in SPA for KR/objective with semantic backend endpoint path and `gemini_analysis` persistence via node updates.
- 2026-02-25: Added Leadership Insights panel in SPA Dashboard with backend leadership metrics fetch plus AI-generated Team Coach and Strategy Pulse summaries.
- 2026-02-25: Closed structured mindmap visualization parity in SPA Atlas inspector (rendered hierarchy with selectable nodes plus raw payload fallback).
- 2026-02-25: Improved leadership parity semantics by adding deterministic Team Coach/Strategy Pulse baselines with AI enrichment overlay in SPA dashboard.
- 2026-02-25: Added semantic backend AI endpoints (`POST /v1/ai/analyze-node`, `POST /v1/ai/team-coach`) with actor-precedence/status-mapping tests and BFF allowlist/proxy coverage to reduce prompt-only parity drift (`backend_app/main.py`, `backend_app/schemas.py`, `tests/test_backend_mutation_api.py`, `spa-bff/test/*`).
- 2026-02-25: Closed HFM-070 by persisting objective analysis payload (`gemini_analysis`) via the same mutation path as KR analysis after `Run Analysis` (`spa-web/src/components/AtlasShell.tsx`).
- 2026-02-25: Closed HFM-073 by replacing prompt-only Strategy Pulse generation with semantic backend workflow (`POST /v1/ai/strategy-pulse`) that reuses Streamlit burnout/gap/predictive services and feeds enriched dashboard fields (burnout score, confidence, mitigation, pivots) with parity tests (`backend_app/main.py`, `backend_app/schemas.py`, `spa-web/src/components/AtlasShell.tsx`, `tests/test_backend_mutation_api.py`, `spa-bff/test/*`).
- 2026-02-25: Tightened Atlas workspace UX: replaced raw cycle-id entry with labeled cycle selector (`Qx-YYYY`/title + active marker), fixed resolved-cycle stale fallback on cycle changes, and enabled automatic Atlas snapshot polling every 45s in Atlas mode (`spa-web/src/components/AtlasShell.tsx`).
- 2026-02-26: Executed Streamlit retirement hard-cut for active runtime: shared package `src/` is canonical, backend bootstrap no longer supports Streamlit path fallback, compose/launchers/docs target SPA stack only.
- 2026-02-27: Completed SPA API client domain split with compatibility barrel (`spa-web/src/lib/api.ts` -> `api/auth.ts`, `api/atlas.ts`, `api/admin.ts`, `api/ritual.ts`, `api/jobs.ts`, shared `api/http.ts`/`api/types.ts`) and extracted Atlas shell navigation contract into a dedicated module (`spa-web/src/components/atlas-shell/navigation.ts`) with parity tests updated.
- 2026-02-27: Continued Wave 5 decomposition by extracting Admin mode UI into dedicated module (`spa-web/src/components/atlas-shell/AdminModePanel.tsx`) and wiring `AtlasShell` as orchestration layer for admin state/actions with parity checks.
- 2026-02-27: Extracted dashboard Leadership Insights subsection into dedicated module (`spa-web/src/components/atlas-shell/DashboardLeadershipPanel.tsx`) and delegated from `AtlasShell` with no behavior contract changes.
- 2026-02-27: Extracted timeline mode UI into dedicated module (`spa-web/src/components/atlas-shell/TimelineModePanel.tsx`) and delegated from `AtlasShell` with existing navigation/filter behavior preserved.
- 2026-02-27: Extracted weekly and daily report modes into dedicated modules (`spa-web/src/components/atlas-shell/WeeklyModePanel.tsx`, `spa-web/src/components/atlas-shell/DailyModePanel.tsx`) and delegated from `AtlasShell` with report/export/query behavior parity checks.
- 2026-02-27: Extracted ritual check-in workflow UI into dedicated module (`spa-web/src/components/atlas-shell/RitualModePanel.tsx`) and delegated from `AtlasShell` while preserving guided stepper, check-in, and experiment lifecycle behavior.
- 2026-02-27: Tightened `RitualModePanel` contract to explicit typed props/state transitions and extracted Retrobox mode UI into dedicated module (`spa-web/src/components/atlas-shell/RetroboxModePanel.tsx`) with delegation and parity checks.
- 2026-02-27: Extracted Atlas Focus Map pane into dedicated module (`spa-web/src/components/atlas-shell/AtlasFocusMapPanel.tsx`) and delegated from `AtlasShell` with tree/list behavior parity checks.
- 2026-02-27: Extracted Atlas top control surface (cycle/owner/mode/lens + validation errors) into dedicated module (`spa-web/src/components/atlas-shell/AtlasModeControlsPanel.tsx`) and delegated from `AtlasShell` with parity checks.
- 2026-02-27: Extracted Inspector AI Assist card into dedicated module (`spa-web/src/components/atlas-shell/InspectorAiAssistPanel.tsx`) and delegated from `AtlasShell` while preserving sync/suggest/undo behavior and error/report rendering.
- 2026-02-27: Extracted Inspector Edit Node + AI Analysis cards into dedicated module (`spa-web/src/components/atlas-shell/InspectorEditAnalysisPanel.tsx`) and delegated from `AtlasShell` with mutation/analysis parity checks.
- 2026-02-27: Extracted Inspector Manage Nodes card into dedicated module (`spa-web/src/components/atlas-shell/InspectorManageNodesPanel.tsx`) and delegated from `AtlasShell` with create-flow parity checks.
- 2026-02-27: Extracted Inspector Task Work History and Objective Alignment cards into dedicated modules (`spa-web/src/components/atlas-shell/InspectorTaskWorkHistoryPanel.tsx`, `spa-web/src/components/atlas-shell/InspectorAlignmentPanel.tsx`) and delegated from `AtlasShell` with parity checks.
- 2026-02-27: Extracted inspector work-history/alignment async state and handlers into dedicated hook (`spa-web/src/components/atlas-shell/useInspectorAuxData.ts`) and reduced `AtlasShell` to orchestration wiring with parity checks.
- 2026-02-27: Extracted node mutation helper contract (`nodeTypeToPath`, `mutationNodeRef`, `createTypeLabel`, `nearestAncestorId`) into `spa-web/src/components/atlas-shell/nodeMutation.ts` and wired `AtlasShell` to shared helpers.
- 2026-02-27: Extracted inspector detail rendering helper (`selectedNodeDetails`) into `spa-web/src/components/atlas-shell/inspectorDetails.ts` and wired `AtlasShell` to shared detail formatter contract.
- 2026-02-27: Added `spa-web` component interaction test stack (`vitest` + `@testing-library/react` + `happy-dom`) with initial inspector panel behavior tests (`InspectorTaskWorkHistoryPanel`, `InspectorAlignmentPanel`) and CI gate (`npm --prefix spa-web test` in `spa-quality`).
- 2026-02-27: Added hook-level behavioral coverage for inspector async orchestration (`spa-web/src/components/atlas-shell/useInspectorAuxData.test.ts`) including alignment/work-log load success/error paths, mutation validation, delete confirmation, and snapshot refresh behavior.
- 2026-02-27: Added focused mutation/analysis interaction tests for inspector edit surface (`spa-web/src/components/atlas-shell/InspectorEditAnalysisPanel.test.tsx`) covering draft field change callbacks, save/delete controls, AI analysis action trigger, and analysis payload rendering.
- 2026-02-27: Added focused AI assist interaction tests for inspector AI surface (`spa-web/src/components/atlas-shell/InspectorAiAssistPanel.test.tsx`) covering action triggers, disabled-state gating, sync report/suggestion rendering, and failure/error/message visibility.
- 2026-02-27: Added focused node-create interaction tests for inspector manage-nodes surface (`spa-web/src/components/atlas-shell/InspectorManageNodesPanel.test.tsx`) covering create-type-specific field rendering (`goal`, `key_result`, `task`), draft patch callbacks, context warnings, and create-button gating.
- 2026-02-27: Added focused top-control interaction tests for Atlas mode controls (`spa-web/src/components/atlas-shell/AtlasModeControlsPanel.test.tsx`) covering callback wiring, cycle input normalization, snapshot pending state, and validation-error rendering.
- 2026-02-27: Added focused dashboard leadership interaction tests (`spa-web/src/components/atlas-shell/DashboardLeadershipPanel.test.tsx`) covering role gating, refresh/generate callback wiring, pending/disabled behavior, and leadership summary/error rendering.
- 2026-02-27: Added focused timeline interaction tests (`spa-web/src/components/atlas-shell/TimelineModePanel.test.tsx`) covering gantt/filter callback wiring, task deep-link action wiring, work-log rendering, and empty-state behavior.
- 2026-02-27: Hardened SPA CI gate order by running `spa-web` build before standalone `typecheck` in `spa-quality` to avoid intermittent `.next/types` drift failures while keeping all gates enforced (`.github/workflows/ci.yml`).
- 2026-02-27: Added focused weekly mode interaction tests (`spa-web/src/components/atlas-shell/WeeklyModePanel.test.tsx`) covering export/AI/save action wiring, weekly draft updates, execution-signal rendering, and pending/empty-state behavior.
- 2026-02-27: Added focused daily mode interaction tests (`spa-web/src/components/atlas-shell/DailyModePanel.test.tsx`) covering export/AI/filter callback wiring, activity-feed rendering, AI-summary rendering, and pending/error/empty-state behavior.
- 2026-02-27: Added focused admin mode interaction tests (`spa-web/src/components/atlas-shell/AdminModePanel.test.tsx`) covering admin-role gating, tab/action wiring for cycle/user/team management, and draft/list mutation callbacks.
- 2026-02-27: Added focused ritual mode interaction tests (`spa-web/src/components/atlas-shell/RitualModePanel.test.tsx`) covering review/check-in/plan step flows, retrospective/check-in/experiment lifecycle actions, and weekly-plan completion callbacks.
- 2026-02-27: Extracted shared date/time formatting and range helpers from `AtlasShell` into `spa-web/src/components/atlas-shell/shellDateUtils.ts` and added direct utility tests (`shellDateUtils.test.ts`) to lock canonical datetime normalization and week/window contracts.
- 2026-02-27: Added SPA coverage gate (`npm --prefix spa-web run test:coverage`) with Vitest thresholds in `spa-web/vitest.config.ts` and enforced it in CI `spa-quality` workflow to prevent silent interaction-test coverage regressions.
- 2026-02-27: Extracted analytics/parsing helper cluster from `AtlasShell` into `spa-web/src/components/atlas-shell/shellAnalyticsUtils.ts` (progress clamps, work-log aggregation, AI summary parsing, leadership baseline shaping) and rewired `AtlasShell` to shared imports.
- 2026-02-27: Added dedicated analytics utility coverage (`shellAnalyticsUtils.test.ts`) for AI decision policy, payload parsing, log aggregation, and deterministic leadership baseline outputs; overall atlas-shell included coverage improved while preserving green SPA gates.
- 2026-02-27: Extracted mindmap/title-resolution helper cluster from `AtlasShell` into `spa-web/src/components/atlas-shell/shellMindmapUtils.ts` (`buildMindmapTree`, fallback-title detection, hierarchical title lookup) and rewired inspector mindmap rendering to shared imports.
- 2026-02-27: Added direct mindmap utility tests (`shellMindmapUtils.test.ts`) for type normalization, hierarchy inference, payload shaping, fallback-title detection, and nested title lookup; atlas-shell coverage increased with no runtime behavior regression.
- 2026-02-28: Extracted shared UI parsing/label/status helpers from `AtlasShell` into `spa-web/src/components/atlas-shell/shellUiUtils.ts` (`parseOwnerIds`, preview bypass parsing, cycle labels, task-status normalization, timeline status labels) and rewired `AtlasShell` to the shared utility imports.
- 2026-02-28: Added direct UI utility coverage (`shellUiUtils.test.ts`) for owner-id validation, preview-bypass parsing, cycle label derivation, and timeline/task status normalization to lock parity while continuing module decomposition.
- 2026-02-28: Extracted dashboard leadership orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useLeadershipInsights.ts` (leadership metrics loader, Team Coach generation, Strategy Pulse generation, and dashboard-mode reset/baseline effects) and rewired shell callbacks to hook outputs.
- 2026-02-28: Added hook-level behavioral coverage for leadership orchestration (`useLeadershipInsights.test.ts`) covering metrics load, baseline seeding, Team Coach fallback on AI failure, Strategy Pulse payload merge, and dashboard-to-non-dashboard reset behavior.
- 2026-02-28: Extracted non-admin mode data orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useAtlasModeData.ts` (weekly/daily/ritual/retrobox/timeline/dashboard loaders plus dashboard/timeline polling+focus refresh wiring) and rewired shell consumers/callbacks to hook outputs.
- 2026-02-28: Added hook-level behavioral coverage for mode-data orchestration (`useAtlasModeData.test.ts`) covering weekly payload wiring, dashboard leadership refresh trigger, in-flight refresh dedupe, and non-atlas mode auto-load behavior; updated static wiring guard to track polling contract at hook location (`tests/test_spa_dashboard_realtime_wiring.py`).
- 2026-02-28: Extracted report/export orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useReportGeneration.ts` (HTML/PDF export flow, AI summary generation flow, and report-state resets) and rewired weekly/daily panel callbacks to hook outputs.
- 2026-02-28: Added shared async job polling helper (`spa-web/src/components/atlas-shell/jobPolling.ts`) and switched Atlas AI suggestion/report flows to that single polling contract; added hook-level report tests (`useReportGeneration.test.ts`) for AI summary success, HTML export path, and PDF fallback behavior.
- 2026-02-28: Extracted timer orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useTimerSession.ts` (start/stop flows, running/elapsed derivation, modal/session lifecycle, snapshot refresh and dashboard/timeline refresh integration) and rewired timer UI controls/modal to hook outputs.
- 2026-02-28: Added timer hook behavioral coverage (`useTimerSession.test.ts`) for start success, stop validation, and stop lifecycle reset/refresh behavior; updated static SPA dashboard wiring guard to track refresh callsite in timer hook (`tests/test_spa_dashboard_realtime_wiring.py`).
- 2026-02-28: Extracted inspector AI progress/suggestion orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useAiProgressAssist.ts` (KR sync preview/apply policy, undo restoration, and async next-task suggestion flow) and rewired shell AI assist handlers/state to hook outputs.
- 2026-02-28: Added AI assist hook behavioral coverage (`useAiProgressAssist.test.ts`) for preview-only sync, apply+undo mutation flow, and next-task suggestion callback wiring.
- 2026-02-28: Extracted inspector node action orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useInspectorNodeActions.ts` (node analysis/save/create/delete flows, selection-driven draft resets, and create-context gating) and rewired inspector panels to hook outputs.
- 2026-02-28: Added inspector node-actions hook behavioral coverage (`useInspectorNodeActions.test.ts`) for analysis persistence, save validation guardrails, create flow selection wiring, and confirmed delete focus-clear behavior; updated static wiring guard to track `nodeTypeToPath`/`mutationNodeRef` callsite in the new hook (`tests/test_spa_dashboard_realtime_wiring.py`).
- 2026-02-28: Extracted ritual write/action orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useRitualActions.ts` (check-in draft initialization, experiment start/close/create flows, check-in validation/submit flow, and ritual state/message handling) and rewired Ritual mode handlers/state to hook outputs.
- 2026-02-28: Added ritual hook behavioral coverage (`useRitualActions.test.ts`) for draft initialization, experiment creation wiring, check-in validation and submit-refresh behavior, and experiment start/close guardrails; added static wiring guard to assert ritual orchestration callsites are owned by `useRitualActions` (`tests/test_spa_dashboard_realtime_wiring.py`).
- 2026-02-28: Extracted admin mutation/action orchestration from `AtlasShell` into dedicated hook `spa-web/src/components/atlas-shell/useAdminActions.ts` (backup export/restore, user/team create-update-delete, password reset, cycle create/activate/delete, and admin draft/message state) and rewired `AdminModePanel` callbacks/state to hook outputs.
- 2026-02-28: Added admin hook behavioral coverage (`useAdminActions.test.ts`) for create-user validation/success flow, backup restore flow, and cycle activation callback wiring; added static wiring guard to assert admin orchestration callsites are owned by `useAdminActions` (`tests/test_spa_dashboard_realtime_wiring.py`).
- 2026-04-10: Added cycle governance and ownership contract hardening across backend/CRUD layers (`owner_manager_id` on cycles, manager/admin-only cycle operations, manager-chain validation for member users, role-scoped cycle resolution for reads/snapshot/leadership queries) with authorization regression coverage (`backend_app/main.py`, `src/crud_*`, `tests/test_backend_mutation_api.py`, `tests/test_crud_authorization.py`).
- 2026-04-10: Upgraded Atlas top controls for role-aware cycle visibility and filtering: managers/admins select owned cycles, members are pinned to manager/admin active cycle, admin owner filter uses searchable pill UX, and lens semantics are standardized to `focus`/`health`/`owner` with deep-link alias normalization (`scope`->`focus`, `branch`->`owner`).
- 2026-04-10: Extended Admin mode governance UX to include cycle owner assignment/update, manager/team/user select inputs, and clearer password reset feedback while preserving admin-gated mutation contracts (`AdminModePanel`, `useAdminActions`, `useAdminResources` + tests).
- 2026-04-10: Fixed first-node creation onboarding gap by keeping Inspector `Manage Nodes` visible without a selected node and defaulting create draft type to `goal`, ensuring first-goal creation is available in empty cycles (`AtlasShell`, `useInspectorNodeActions` + test coverage).
- 2026-04-10: Hardened local hybrid launcher and BFF edge behavior: launcher now waits for backend warm-up, tracks spawned PID health, and auto-falls back to local SQLite when remote DB is unreachable; BFF login now returns normalized invalid-credential responses and strips empty-body `content-type` forwarding.
