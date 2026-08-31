# User Guide
Documentation HQ: [README](../README.md)

This guide describes the current SPA-first behavior implemented in `spa-web/`, `spa-bff/`, `backend_app/`, and shared domain modules under `src/`.

Learning Loop canonical guide (EN+FA, synced headings): [`docs/learning-loop.md`](learning-loop.md).

## 1. Atlas Workspace as Your Cockpit

The main execution workspace is Atlas (`render_atlas_workspace`), composed of:
- Focus Task strip
- Focus Map tab
- Inspector tab

### Focus Task strip
- Shows a suggested next task based on urgency and execution context.
- Lets you start/stop timer sessions and capture a short session summary.
- Timer authorization follows canonical goal-owner scope.
- Supports sprint presets (`25m`, `50m`, `Custom`).
- `Use Suggested` sets both focus task and current selection.

### Focus Map tab
- Quick Jump search for any goal/objective/KR/task.
- Cycle selector is role-aware:
  - Admin can select any visible cycle; managers can select their owned cycles and admin-owned global cycles.
  - Members resolve to their manager's active cycle, with an active admin-owned global cycle as fallback.
- Owner filter is available for admin users to narrow Atlas reads.
- Map Lens supports `Focus`, `Health`, and `Owner` views.
- Map key includes:
  - Performance bands for Goals/Objectives/KRs: `0.0-0.3 Missed`, `0.4-0.6 At Risk`, `0.7-0.9 On Track`, `1.0 Superstar`.
  - Health labels for task/branch state: `Needs care`, `On track`, `Complete`.

### Inspector tab
- Opens details for the selected node.
- Use it for edits, lifecycle updates, alignment links, and task schedule/work history.
- On empty hierarchies, `Manage Nodes` still appears so you can create the first `Goal` without pre-selecting a node.

### 1.1 Goal vs Objective vs KR (Use Before Editing)

- `Goal`: why this strategic change matters and what strategic direction it sets.
- `Objective`: what changed state should exist by cycle end.
- `KR`: how that changed state is proven numerically.

Classification shortcut:
- If it expresses purpose/direction and intended strategic shift -> `Goal`.
- If it is a strategic outcome that needs multiple indicators -> `Objective`.
- If it is one measurable line (`from A to B by date`) -> `KR`.
- If it is an action step -> task/initiative (not objective/KR evidence).

OKR time boundaries:
- Goals and Objectives are time-bounded by the OKR cycle, NOT by individual deadlines.
- Only Key Results have measurable progress (measured through check-in sessions).
- Only Tasks have deadlines.

Common writing mistakes:
- Objective written as a single metric line -> should be a KR.
- KR written as broad narrative ("improve experience") -> should be an objective.
- Task completion text in KR check-ins -> not valid KR evidence without metric delta.

## 2. How KR Updates Actually Work

KR progress is driven by KR metric values (`start_value`, `current_value`, `target_value`) and score logic.
Task completion alone does not directly set KR metric values.

You can update KRs manually in two ways:
- Weekly Check-In -> Step 2 `Update KRs` creates a check-in (`create_check_in`) with value, confidence, and comment.
- Inspector on a KR -> edit Start/Current/Target values (and metric type/unit) directly.

Important:
- `get_krs_needing_checkin` lists ACTIVE KRs with stale/missing check-ins.
- DRAFT objectives/KRs are excluded from rollups.
- **Every check-in now requires variation classification** (see Learning Loop below).

### 2.1 Critical Boundary: OKRs vs BAU (Do Not Mix)

Rule:
- If a task would happen the same way without this cycle's Objective/KR, it is BAU and should not be counted as strategic progress.
- Deadline or urgency does not make a task strategic; it can still be BAU.

10-second self-check:
1. "Would my manager ask this even without an OKR?" -> Yes means BAU.
2. "Can I write the KPI movement from A to B by date?" -> No means BAU.
3. "Am I reporting activity count instead of KPI shift?" -> Yes means BAU.

Use this fast `SHIFT` check before writing KR updates:
- `S` (System change): does this change how work is done?
- `H` (Hypothesis): is there a testable prediction?
- `I` (Insight): will it produce reusable learning?
- `F` (Frequency): is it recurring regardless of strategy?
- `T` (Target delta): should a baseline KPI move materially?

Member decision shortcut:
- Mostly routine + recurring (`F` yes, weak `S/H/T`) -> treat as BAU.
- Time-boxed change with measurable KPI delta (`S/H/T` yes) -> keep in OKR.

Weekly practice for members:
1. Log suspected routine work in the external BAU governance note/release log (not in app check-in comment fields).
2. Keep BAU notes transparent in that external artifact; do not frame them as KR attainment.
3. Ask manager to classify in weekly review (`release to BAU` vs `convert to true OKR change`).
4. If manager assigns BAU work with deadlines, track it in the operational lane (for example Odoo/ticketing/paper list), not as OKR-progress evidence.
5. Keep two separate sections in external weekly governance notes: `Strategic lane` and `Operational lane`.

Important boundary:
- Do not add BAU classification markers into KR check-in forms; check-ins remain for KR metric + learning-loop data.

Example rewrite:
- Weak: "Handled daily support tickets."
- Strong: "Reduced incoming support tickets per active user by launching self-service flow."

Policy reference:
- `docs/OKR_BAU_BOUNDARY_GUIDE.md`

## 3. Learning Loop: Variation Classification & Experiments

The Learning Loop transforms weekly check-ins from passive reporting into active system improvement.

### 3.1 Variation Classification

Every KR check-in requires classifying the metric change:

| Type | Meaning | When to Use |
|------|---------|-------------|
| **Common Cause** | Normal system behavior | Regular fluctuations within expected range |
| **Special Cause** | Exceptional event | One-time events, outages, external factors |

**Common Cause flow:**
- Optionally link to an active experiment (if testing a change)
- If no experiment exists, you can create one inline

**Special Cause flow:**
- Must provide a note (min 5 characters) explaining the exceptional event
- Cannot link to experiments (special causes are not controlled tests)

### 3.2 Experiment Lifecycle

Experiments are first-class artifacts linked to Key Results:

| Status | Description |
|--------|-------------|
| `PLANNED` | Experiment defined but not started |
| `RUNNING` | Experiment in progress |
| `DECIDED` | Experiment concluded with a decision |

Decisions:
| Decision | Meaning |
|----------|---------|
| `ADOPT` | Keep the change permanently |
| `REVERT` | Roll back the change |
| `ITERATE` | Modify and retry |
| `UNKNOWN` | Inconclusive results |

### 3.3 Experiment Review in Weekly Check-In

**Step 1 (Review Week):**
- Shows experiments that ended this week OR are still RUNNING
- For each experiment, record decision and rationale
- Decision updates both `RetroExperimentOutcome` AND closes the experiment (status â†’ DECIDED)

**Step 2 (Update KRs):**
- Classify variation type for each check-in
- Link to active experiment (if Common Cause)

### 3.4 Creating Experiments

From KR check-in (Common Cause flow):
1. Click "Start New Experiment"
2. Fill: hypothesis ("If we do X, then Y will happen"), change description, expected direction/effect
3. Submit creates experiment and sets status to RUNNING

## 4. Weekly Check-In vs Retrospective (Clearly Distinguished)

Weekly Check-In (`active_report_mode = "Check-In"`) is a 3-step guided flow:
1. Review Week: work-log recap, optional AI summary, and retrospective text input.
2. Update KRs: check-ins for KRs that need updates.
3. Plan Next Week: set top 3 priorities (`WeeklyPlan`).

Retrospective entry:
- Captured in Check-In Step 1 (`create_retrospective`).
- RetroBox is a viewer for saved retrospectives; it is not the KR-update flow.

Timing:
- The app does not enforce exact weekdays.
- Recommended cadence: run Check-In once per week and review RetroBox after submission.

## 4. Reports: Process and Timing by Report Type

Daily Report:
- Time window: today since local midnight.
- Best use: end-of-day execution recap.

Weekly Report:
- Time window: last 7 days.
- Adds optional AI weekly brief and weekly trend chart.

Both report types:
- Source data: work logs tied to tasks.
- Include detailed log table, objective time distribution, and deadline health.
- Export: PDF via `PDF_METHOD=pdfshift` or `PDF_METHOD=chromium`; if renderer is unavailable, HTML fallback is offered.

Technical note:
- In backend-segregated deployments, frontend read and write operations route through `backend-api` (`OKR_BACKEND_PROXY_MUTATIONS=true`, `OKR_BACKEND_PROXY_READS=true`) including node CRUD, timer, user/cycle/team admin actions, Learning Loop writes, alignments, and read-heavy Atlas/leadership queries.
- Report AI/PDF generation runs through internal async jobs (`backend-api` + `backend-worker`).
- If backend transport is unavailable, runtime behavior is fail-closed (no local mutation/read fallback execution).

## 5. Strategic Dashboard (What It Actually Shows)

Strategic Dashboard (`active_report_mode = "Dashboard"`) includes:
- Key metrics: Data Hygiene, Avg Confidence, At-Risk KRs, Overdue Tasks, At Risk Tasks.
- Team filter for managers/admins.
- Progress by team member.
- Deadline health by member.
- Strategic Alignment Matrix (efficiency vs effectiveness, colored by confidence).
- At-risk KR list.
- Overdue task list.
- Optional AI Team Coach section (manager/admin).

Leadership Insights dialog structure:
- `Execution` tab: KPI cards, risk lists, team distribution, AI Team Coach.
- `Strategy Pulse` tab: burnout indicator, ghost-goal gap scan, AI predictive forecast, and achievement portfolio PDF export.
- Managers should use both tabs together: monitor execution in `Execution`, then decide coaching/rebalancing interventions from `Strategy Pulse`.

Use this view for weekly governance and escalation, not for deep field editing.

## 6. Project Timeline and Other Tools

Project Timeline dialog:
- Renders a Gantt chart from task data.
- Visualizes start, finish/deadline fallback, and status colors.

Current implementation note:
- Timeline is strictly scoped to an authorized cycle and role visibility:
  - Member: their manager's active cycle, with an active admin-owned global cycle as fallback.
  - Manager: selected owned cycle or an admin-owned global cycle.
  - Admin: any visible cycle.

Other useful tools:
- Weekly Focus card in sidebar for top 3 priorities.
- Weekly Check-In + Reports for personal execution loop.
- Strategic Dashboard for team-level monitoring.

## 7. Inspector Quick Reference

Goal:
- Narrative direction and intent: why this change matters and what strategic shift it points to.
- Title, description, cycle assignment, strategy tags.

Objective:
- Strategic outcome: what should be different by cycle end.
- Title/description, score mode, weight, lifecycle state, final reflection, alignment links.

Key Result:
- Numeric proof: how objective movement is verified (`start/current/target` over time).
- Start/Target/Current values, unit, metric type, weight, lifecycle state, final reflection, initiative tags.
- AI analysis run action from Inspector.

Task:
- Title/description/progress, assignee (role-based), start date, due date, deadline status.
- Work History list with delete-log action.

## 8. Recommended Weekly Operating Rhythm

1. During week: run Focus Task timer and keep task summaries clean.
2. End of week: complete Weekly Check-In (all three steps).
3. After Check-In: review Weekly Report and export if needed.
4. Managers/admins: review Strategic Dashboard (`Execution` + `Strategy Pulse`) and RetroBox.

## 9. Tool-by-Tool Process and Timing Matrix

Timing note:
- The app does not hard-enforce weekdays. The table below is the operational cadence recommended for a SCRUM-inspired OKR loop.

| Tool / Feature | Primary Owner | Process | Recommended Timing | Frequency | Expected Output |
|---|---|---|---|---|---|
| Focus Task (Atlas) | Member / Manager / Admin | Pick one task, run sprint timer, stop with summary. | Start of each focused work block. | Multiple times per day. | Work logs with clear execution evidence. |
| Focus Map + Map Lens | Member / Manager / Admin | Select an authorized cycle when applicable, optionally filter owners (admin), switch `Focus`/`Health`/`Owner`, identify `Needs care`. | At session start and when priorities shift. | Daily. | Clear next branch/task decision. |
| Inspector | Role-authorized user | Edit node fields (KR metrics, lifecycle, assignments, dates). | Immediately when data quality gaps are found. | Ad hoc (usually daily/weekly). | Correct and auditable OKR data. |
| Lifecycle & Closing (Inspector) | Objective/KR owner, Manager, Admin | Move state (`DRAFT/ACTIVE/GRADING/ARCHIVED`) and capture reflection. | At phase boundaries of the quarter. | Few times per quarter. | Valid state transitions and closure notes. |
| Organizational Alignment (Objective Inspector) | Manager / Admin (or authorized owner) | Add/remove objective alignment edges with cycle-safe validation. | During planning and mid-quarter replanning. | Weekly or milestone-based. | Traceable cross-objective dependencies. |
| Weekly Check-In | Member / Manager / Admin | 3 steps: Review Week, Update KRs, Plan Next Week. | End of work week. | Weekly. | KR check-ins, retrospective entry, next-week priorities. |
| RetroBox | Member / Manager / Admin | Review stored retrospectives (personal/team). | After Weekly Check-In and in weekly team review. | Weekly. | Reflection visibility and coaching input. |
| Daily Report | Member / Manager / Admin | Open `Daily Report` (today window) and review execution. | End of day. | Daily. | Day-level execution summary and export. |
| Weekly Report | Member / Manager / Admin | Open `Weekly Report` (7-day window), generate optional AI brief, export. | End of week after Check-In. | Weekly. | Week-level summary, trends, and artifacts. |
| Strategic Dashboard | Manager / Admin (member in own scope) | Review KPI cards, risk lists, matrix, and team distribution. | Weekly governance meeting; also mid-week if risk spikes. | Weekly + event-driven. | Prioritized interventions and escalation decisions. |
| Strategy Pulse (Leadership Insights) | Manager / Admin | Review burnout risk, ghost-goal gaps, AI forecast, and generate Achievement Portfolio PDF. | Immediately after reviewing Strategic Dashboard execution signals. | Weekly + on risk spikes. | Early risk detection, team coaching actions, and reusable leadership evidence pack. |
| AI Progress Sync (Atlas sidebar) | Manager / Admin | Run preview first, then apply bounded sync if needed; use undo when necessary. | After major KR analysis refresh or before governance review. | Weekly or as needed. | Consistent KR analysis/progress refresh under policy controls. |
| Project Timeline | Member / Manager / Admin | Review gantt view of tasks and deadline shape. | Sprint planning and when deadlines move. | 1-2 times per week. | Schedule clarity and deadline risk awareness. |
| Weekly Focus Card (Sidebar) | Member / Manager / Admin | Set/track top 3 priorities from Weekly Check-In plan. | Start of week and daily check-in. | Weekly + daily glance. | Stable weekly execution focus. |

## 10. Manager Visibility + Privilege Clarification

How managers see team OKRs/tasks:
1. In Atlas Focus Map, choose a cycle where you are assigned as cycle owner.
2. In Strategic Dashboard, use team/member filter.
3. In Project Timeline, manager sees role-filtered team-visible tasks for the selected owned cycle or global cycle.

Read/Edit/None rules (current behavior):
1. Manager read: own nodes + direct-report nodes + same-team visibility.
2. Manager edit/delete: own nodes + direct-report nodes (manager-of-owner rule).
3. Member: own-scope only.
4. Admin: full scope.

Gemini retrieval boundary:
1. AI analysis calls pass actor identity from UI.
2. Node reads can be actor-scoped (`get_node(..., actor_username=...)`) and are checked against `READ` permission.
3. AI output writes still require normal mutation authorization.

Manager step-by-step operating guide:
- [Manager Playbook](MANAGER_PLAYBOOK.md)
