# System Administrator Guide
Documentation HQ: [README](../README.md)

This guide is aligned with current behavior in the codebase (`streamlit_app/app.py`, `streamlit_app/src/ui/*`, `streamlit_app/src/crud.py`, `streamlit_app/src/domain/*`).

## 1. RBAC and Mutation Rules

User roles:
- `admin`: full organization visibility, user/cycle administration, broad edit rights.
- `manager`: visibility and mutation scope for direct-report hierarchies, plus weekly team monitoring, coaching, and ritual discipline.
- `member`: own-scope execution and updates.

Direct-report vs same-team (important distinction):
- `direct-report`: the node owner directly reports to the manager (`owner.manager_id == manager.id`).
- `same-team`: the node owner shares `team_id` with the manager but may report to another manager.
- Why this split exists: team-level situational awareness needs broader visibility, but write authority should stay with accountable line management.
- Current manager policy:
  - `READ`: own + direct-report + same-team.
  - `UPDATE/DELETE`: own + direct-report only (`manager-of-owner`).

Mutation guardrail:
- Goal-scoped write operations pass authorization checks (`_authorize_goal_mutation`).
- Objective alignment writes (`create_alignment` / `delete_alignment`) are authorized before commit.
- AI/Inspector node retrieval can use actor-scoped read checks (`get_node(..., actor_username=...)`) to enforce `READ` permissions.

## 2. Admin Control Surfaces

Primary admin surfaces in UI:
- `Admin Panel` dialog: user administration, resets, cycle management tasks, and `AI Health` checks.
- `Atlas Workspace`: role-aware scope selection (`All Users` for admin), Focus Map, Inspector.
- `Strategic Dashboard`: aggregate team metrics and risk surfacing.

### Atlas as Admin Cockpit

Inside Focus Map sidebar (admin scope), you can run:
- `AI Progress Sync`
- `Preview mode (no writes)`
- `Apply AI overall score to KR progress`
- `Max KR progress delta`
- `Allow progress decreases`
- `Undo Last AI Progress Apply` (time-limited)

Use this cockpit for controlled sync and correction, not blind bulk updates.

### Runtime Architecture for Admin Operators

Current recommended deployment topology:
- `okr` (Streamlit UI/session workflow shell)
- `backend-api` (internal timer + job control plane)
- `backend-worker` (async execution for AI/PDF jobs)
- shared Supabase PostgreSQL database

Key wiring:
- `OKR_BACKEND_API_URL` from `okr` -> `backend-api`
- `OKR_BACKEND_SERVICE_TOKEN` must match across caller and backend API
- backend API should remain private/internal, not internet-exposed

## 3. Lifecycle and Rollup Rules You Must Enforce

For Objectives and KRs:
- States: `DRAFT`, `ACTIVE`, `GRADING`, `ARCHIVED`.
- Objective activation requires at least one KR.
- Objective state changes cascade to child KRs.
- `DRAFT` items are excluded from score rollups.

Scoring model:
- KR score derives from `start_value`, `current_value`, `target_value`, `metric_type`.
- Objective score mode can be `UNWEIGHTED` or `WEIGHTED`.
- Goal rollup uses objective progress/weights.

## 4. Weekly Operating Routine (Admin)

1. Confirm correct active cycle and user assignments.
2. Open Strategic Dashboard and review:
   - `Data Hygiene`
   - `Avg Confidence`
   - `At-Risk KRs`
   - `Overdue Tasks`
   - `At Risk Tasks`
3. Review `At-Risk Key Results` and `Overdue Tasks` lists.
4. Use Atlas scope + branch lens to identify exact correction points.
5. Run `AI Progress Sync` only when analysis refresh is needed, preferably in preview first.
6. In `Leadership Insights -> Strategy Pulse`, review burnout/gap signals and drive manager coaching or workload rebalance actions.

### Dummy Manager Team-Monitoring Runbook (Step-by-Step)

Use this when validating manager-role behavior in sandbox/UAT with dummy accounts.

For the full manager operating model (visibility, privilege matrix, report timing, and UAT script), use:
- [Manager Playbook](MANAGER_PLAYBOOK.md)

Setup prerequisites (admin):
1. Create a dummy manager user with role `manager` and an assigned `team_id`.
2. Create 3-5 dummy members and set each `manager_id` to that dummy manager.
3. Ensure an active cycle exists and each dummy member has at least one Goal -> Objective -> KR.
4. Move Objectives/KRs from `DRAFT` to `ACTIVE` so they are visible in monitoring rollups.

Weekly monitoring procedure (dummy manager):
1. Baseline (start of week): open `Leadership Insights -> Execution`, filter to the manager's team, record `Data Hygiene`, `Avg Confidence`, `At-Risk KRs`, `Overdue Tasks`, `At Risk Tasks`.
2. Mid-week control: review `At-Risk Key Results` and `Overdue Tasks`; open affected nodes in Atlas (`Branch` lens) and correct ownership, deadlines, or KR metric fields where required.
3. Ritual governance (end of week): verify every direct report completes `Weekly Ritual` (Step 2 KR check-ins + Step 3 weekly plan). Treat `RetroBox` as review-only evidence, not an update flow.
4. Strategic risk pass: open `Strategy Pulse`, review burnout + ghost-goal gaps, then generate AI forecast and mitigation actions.
5. Coaching and escalation: convert high-risk items into explicit team actions (owner + due date + expected metric effect); escalate systemic blockers to admin.
6. Evidence closure: export `Weekly Report` and keep one shareable summary artifact for the weekly manager review.

Role boundaries for dummy managers:
1. Allowed scope: direct-report hierarchy and assigned team context.
2. Not allowed: cross-team/global edits reserved for `admin`.

Definition of done (for manager monitoring quality):
1. Ritual completion rate for direct reports is 100% weekly.
2. No ACTIVE KR remains without fresh check-in beyond policy threshold.
3. Every high-risk KR has a named owner, mitigation action, and follow-up date.

## 5. Ritual, Retro, and Reporting Governance

Process distinction:
- `Weekly Ritual` is the KR update workflow (check-ins + weekly plan).
- `Retrospective` text is captured in Ritual step 1.
- `RetroBox` is for viewing saved retrospectives (personal/team), not KR check-ins.

Report timing:
- `Daily Report`: today window.
- `Weekly Report`: last 7 days window.
- Both are work-log based and exportable (`pdfshift` PDF path with HTML fallback).

## 6. Incident Playbooks

### A) KR looks stale or inconsistent
1. Open KR in Inspector; verify `start/current/target` values and metric type.
2. Confirm recent check-ins exist (Weekly Ritual step 2).
3. If needed, update KR manually, then re-open dashboard to verify rollup.

### B) Wrong hierarchy or assignment
1. Open Task in Inspector.
2. Correct assignee/schedule fields.
3. If parent linkage is wrong, move/recreate under correct KR using Atlas actions.

### C) Team risk spike (many overdue/at-risk tasks)
1. Use dashboard lists to isolate owners and areas.
2. Use branch lens in Atlas to focus one objective tree at a time.
3. Ask managers to complete Weekly Ritual and raise confidence-quality comments.

## 7. Known Limits (Important)

Current UI does not provide:
- a dedicated `Global Sync Status` or `Refresh All` page,
- a work-log pencil-edit workflow (delete/re-log is the available correction path),
- KR updates from RetroBox (RetroBox is view-only).

Current timeline note:
- Project Timeline is now strictly cycle-bounded (`active_cycle_id`) and role-filtered for visibility (member/manager/admin scopes).

## 8. Quick Audit Checklist

1. RBAC correctness (admin/manager/member scopes).
2. Active cycle correctness and overlap sanity.
3. DRAFT items moved to ACTIVE when execution starts.
4. Weekly Ritual adoption for KR check-ins.
5. Dashboard risk trends reviewed and acted on.
6. AI sync used with preview-first discipline.

## 9. Admin Tool Process and Timing Matrix

Timing note:
- Cadence below is recommended governance rhythm. The application does not enforce fixed weekdays.

| Tool / Feature | Primary Owner | Process | Recommended Timing | Frequency | Expected Output |
|---|---|---|---|---|---|
| Admin Panel | Admin | Manage users, reset passwords, perform admin controls. | Onboarding/offboarding and incident response windows. | Ad hoc. | Access hygiene and operational continuity. |
| Manage Cycles | Admin | Create/activate/deactivate cycles and confirm active period. | Pre-quarter setup and quarter close transition. | Quarterly (or when needed). | Correct cycle boundaries and active scope. |
| Strategic Dashboard | Admin / Manager | Review KPI cards, at-risk KR list, overdue tasks, team distribution. | Weekly governance review; mid-week on risk spikes. | Weekly + event-driven. | Ranked intervention plan. |
| Strategy Pulse (Leadership Insights tab) | Admin / Manager | Review burnout risk, strategy gaps, predictive outlook, and achievement portfolio artifacts to guide intervention/coaching. | After reviewing Strategic Dashboard execution metrics. | Weekly + on risk spikes. | Proactive capacity decisions and leadership coaching plan. |
| Team Filter (Dashboard) | Admin / Manager | Isolate members/teams to identify root-cause patterns. | During dashboard review. | Every review session. | Targeted coaching and accountability. |
| Atlas Inspector (Data Correction) | Admin / Manager | Correct KR metrics, lifecycle states, assignments, and deadlines. | Right after anomaly detection. | Ad hoc (often weekly). | Clean, defensible operational data. |
| AI Progress Sync (Atlas) | Admin / Manager | Run preview, apply bounded update, verify result, use undo if needed. | After analysis refresh or before executive check-in. | Weekly or as needed. | Controlled organization-wide analysis/progress consistency. |
| AI Team Coach (Dashboard) | Admin / Manager | Generate coaching guidance from aggregate team metrics. | After dashboard metrics review. | Weekly. | Actionable coaching priorities and quick wins. |
| Weekly Ritual Compliance Review | Manager / Admin | Verify teams complete Ritual and update KR check-ins. | End-of-week governance cycle. | Weekly. | Reliable check-in cadence and better forecast quality. |
| RetroBox (Team Retros) | Manager / Admin | Review team retrospectives and identify systemic blockers. | Post-Ritual team review. | Weekly. | Documented improvement loop and impediment list. |
| Weekly Report (Team/Owner context) | Admin / Manager | Use report outputs for evidence in reviews and escalations. | End of week, after Ritual. | Weekly. | Shared factual summary artifacts. |
| Project Timeline | Admin / Manager | Validate schedule pressure and deadline clustering by task. | Sprint planning and incident triage. | 1-2 times per week. | Deadline risk visibility for capacity decisions. |

## 10. Secrets and Runtime Configuration

For production stability:
1. Keep AI credentials in Streamlit secrets or secure environment variables, never in repository files.
2. Set `AI_PROVIDER` explicitly (`gemini` or `openai_compatible`) and verify via `Admin Panel -> AI Health` or `python streamlit_app/scripts/ai_provider_health_check.py`.
3. If using Gemini, set `GEMINI_API_KEY`.
4. For PDF export, use `PDF_METHOD=pdfshift` with a valid PDFShift API key from secrets.
5. HTML export remains available when PDF rendering is not configured.
6. Keep one deployment mode active per environment (avoid mixed pipelines in the same runtime).
7. Optional fail-fast mode: set `OKR_STRICT_RUNTIME_PREFLIGHT=1` to stop app startup when runtime preflight detects critical runtime misconfiguration.
