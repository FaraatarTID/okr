# Manager Playbook
Documentation HQ: [README](../README.md)

This playbook is a manager-operating guide for the current implementation in `streamlit_app/src/ui/*`, `streamlit_app/src/crud.py`, and `streamlit_app/src/services/ai_service.py`.

For organization-wide rollout design, also use `docs/OKR_ROLLOUT_GUIDE.md`.
For strict strategic-change vs BAU classification, use `docs/OKR_BAU_BOUNDARY_GUIDE.md`.

## Introduction (Why This Exists Beside Conventional Management)

This playbook is not a replacement for conventional management. It is a second operating system with a different job:
- Conventional management: deliver commitments, hit deadlines, protect SLA, keep operations stable.
- OKR management: change how the system performs, move KPI baselines, and create reusable learning.

If you merge these two jobs, teams become busy but strategy becomes invisible.

Manager non-negotiable:
1. BAU assignments can be urgent and deadline-driven.
2. Urgency and deadlines still do not make BAU strategic.
3. Only verified KPI baseline movement is valid OKR progress evidence.
4. BAU classification/release is managed outside the app (no BAU data-entry requirement in KR check-ins).

## 1. Manager Role in This System

Manager role is expected to own three responsibilities:
- Team monitoring: track execution quality, risk, and check-in discipline.
- Team building/coaching: remove blockers, rebalance workload, and improve KR quality.
- Leadership escalation: convert risks into actions and escalate systemic constraints to admin.

## 2. Preconditions (Visibility + Control)

A manager can monitor and act only when all are true:
1. User role is `manager`.
2. Team members are linked by `manager_id = <manager user id>`.
3. Team has active Goals/Objectives/KRs in the active cycle.
4. Objectives/KRs are moved from `DRAFT` to `ACTIVE` when execution starts.

## 3. How Managers See Team OKRs and Tasks

Atlas Workspace (`Focus Map`):
1. Open `Scope selector`.
2. Use `My Team` to load manager + direct reports.
3. Optionally switch to a specific member scope.
4. Use `Branch` lens to drill one objective subtree.

Leadership Insights (`Strategic Dashboard`):
1. Open dashboard.
2. Apply team/member filter.
3. Review KPI cards + risk lists + strategy pulse.

Project Timeline:
1. Open timeline dialog.
2. It is role-filtered, so manager sees team-visible tasks for active cycle.
3. Use for deadline clustering and capacity pressure review.

Inspector:
1. Select node from Focus Map.
2. Review or edit fields according to RBAC.
3. Use `Organizational Alignment` for objective links (authorized roles only).

## 4. Read/Edit/None Privilege Model

| Context | Admin | Manager | Member |
|---|---|---|---|
| Own nodes | Read/Edit | Read/Edit | Read/Edit |
| Direct-report nodes | Read/Edit | Read/Edit | None |
| Same-team non-report nodes | Read/Edit | Read (no edit unless manager-of-owner) | None |
| Other-team nodes | Read/Edit | None | None |
| User/cycle administration | Read/Edit | None | None |
| Team coaching dashboards | Read/Edit | Read/Edit (team scope) | Own scope only |
| Gemini node retrieval (`analyze_node`) | Read per admin scope | Read per manager scope | Read per own scope |

Implementation note:
- Manager `READ` allows direct-report and same-team visibility.
- Manager `UPDATE/DELETE` requires manager-of-owner (or ownership).

## 5. Gemini Data Access and Safety

Current hardening in code:
1. UI passes actor identity into AI analysis calls.
2. `analyze_node(...)` fetches nodes through RBAC-aware read path (`get_node(..., actor_username=...)`).
3. Node read is authorized before prompt context is assembled.
4. AI result writes still pass standard mutation authorization (`update_key_result(..., actor_username=...)`).
5. Alignment add/remove now requires mutation authorization on involved objective goals.

Result:
- Gemini cannot be used as a bypass to read unauthorized nodes through normal UI flows.

## 6. Weekly Process and Timing (SCRUM-inspired OKR)

Timing note:
- The app does not enforce fixed weekdays. Cadence below is recommended operating rhythm.

Recommended manager rhythm:
1. Start-of-week (planning): review `Strategy Pulse`, confirm top 3 interventions, validate Weekly Focus priorities.
2. Mid-week (control): review overdue/at-risk lists, open Inspector, correct ownership/deadlines/metrics as needed.
3. End-of-week (ritual governance): verify all direct reports complete Weekly Ritual (Review Week -> Update KRs -> Plan Next Week).
4. Post-ritual review: read RetroBox and Weekly Report, then prepare coaching/escalation summary.

## 7. BAU Release Gate (Mandatory Weekly)

Managers must actively prevent BAU contamination in OKRs.

Weekly BAU release workflow:
1. Collect BAU candidates from external governance inputs (manager notes, ops backlog, Odoo/ticketing/paper trackers).
2. Classify each candidate using `SHIFT` test from `docs/OKR_BAU_BOUNDARY_GUIDE.md`.
3. Decide one outcome:
   - `RELEASE_TO_BAU`: move to operations backlog/KPI tracking.
   - `CONVERT_TO_OKR_CHANGE`: rewrite as hypothesis-driven change initiative.
   - `KEEP_IN_OKR`: only when strategic delta is explicit and evidence-backed.
4. Record decisions in:
   - `docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md`
5. Review contamination trend monthly with admin.

Dual-track weekly ritual rule:
1. Strategic lane:
   - KR check-ins and change commitments that can affect OKR interpretation.
2. Operational lane:
   - BAU assignments with owners and deadlines, tracked in operational systems (for example Odoo ERP, ticketing/project platforms, or paper logs).
3. Never merge lanes:
   - BAU completion is not KR progress evidence.
   - BAU deadline pressure does not make work strategic.
   - If BAU work starts changing KPI baseline, explicitly convert it into a strategic KR change initiative.

60-second ritual opening script (read verbatim):
1. "This meeting has two lanes: Strategic lane for change and Operational lane for operations."
2. "BAU items may have strict deadlines and owners, but they remain BAU."
3. "In this room, activity volume is not strategy evidence."
4. "Only KPI baseline movement counts as OKR progress."
5. "If an item is unclassified, we stop and classify it before closing the ritual."

Mandatory weekly output format (external governance artifact, not in-app KR fields):
- Strategic lane section: `<change commitment + expected KPI delta>`
- Operational lane section: `<assignment + owner + deadline + execution system/reference>`
- Items outside these two sections are invalid until classified.

Manager red flags:
- Repeating throughput tasks reported as KR progress.
- Objectives that describe "run operations" rather than "change system behavior."
- Check-ins with activity volume but no KPI delta.

## 8. Reports by Type (Manager Usage)

Daily Report:
- Window: current day.
- Use: short execution health pulse and blocker detection.

Weekly Report:
- Window: last 7 days.
- Use: governance evidence pack after ritual completion.

Ritual vs Retro:
- KR updates happen in Weekly Ritual step 2.
- RetroBox is review-only for saved retrospectives.

## 9. Manager Role During Enterprise Rollout (Pilot -> Scale)

When the company is introducing OKRs beyond one team, managers should run an explicit pilot-to-scale discipline.

Pre-pilot manager checks:
1. Confirm direct reports are correctly linked (`manager_id`) and visible in `My Team`.
2. Confirm team Objectives/KRs are ready to move from `DRAFT` to `ACTIVE` at kickoff.
3. Confirm weekly check-in, review, and retrospective meetings are scheduled before cycle start.
4. Confirm training/coaching plan is complete for your team members.

Pilot-cycle execution responsibilities:
1. Keep Weekly Ritual completion rate high and resolve stale check-ins immediately.
2. Use Inspector to maintain KR metric quality (`start/current/target`, confidence comments, deadlines).
3. Convert risk signals from dashboard into concrete interventions (ownership, scope, deadline, unblockers).
4. Capture objective/KR closure reflections to produce reusable learning for next cycle.

Scale recommendation package (what managers should hand upward after pilot):
1. Evidence of adoption (ritual completion, check-in freshness, participation quality).
2. Evidence of outcome quality (risk trend, confidence trend, KR attainment signals).
3. Top blockers that require leadership or cross-team decisions.
4. Clear recommendation: keep scope, expand to next teams, or extend pilot.

## 10. Dummy Manager UAT Script (Step-by-Step)

1. Admin setup: create one dummy manager and 3-5 direct reports (`manager_id` linked).
2. Seed active cycle: ensure each member has Goal -> Objective -> KR -> Task chain.
3. Activate execution: move Objective/KR state to `ACTIVE`.
4. Visibility check:
   - manager opens Atlas
   - `My Team` scope shows team nodes
   - outsider scope is not exposed
5. Edit check:
   - manager edits one direct-report KR metric in Inspector (should pass)
   - manager edits outsider goal/KR (should fail with permission error)
6. AI check:
   - manager runs KR analysis on direct-report node (should pass)
   - manager attempts analysis on unauthorized node id (should fail authorization)
7. Ritual check:
   - each report submits KR check-in in Ritual step 2
   - manager verifies completion + confidence quality
8. Evidence closure:
   - export Weekly Report
   - keep one summary artifact for admin review

## 11. Troubleshooting

If manager cannot see team nodes:
1. Verify `manager_id` links on users.
2. Verify there is an active cycle.
3. Verify objectives/KRs are not left in `DRAFT`.
4. Verify manager selected `My Team` (not `My OKRs`) in Atlas scope selector.

If manager can see but cannot edit:
1. Confirm node owner is direct report (manager-of-owner edit rule).
2. Confirm account is active and role is `manager`.
3. Check permission errors in UI and audit logs.
