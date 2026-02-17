# Manager Playbook
Documentation HQ: [README](../README.md)

This playbook is a manager-operating guide for the current implementation in `streamlit_app/src/ui/*`, `streamlit_app/src/crud.py`, and `streamlit_app/src/services/ai_service.py`.

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

## 7. Reports by Type (Manager Usage)

Daily Report:
- Window: current day.
- Use: short execution health pulse and blocker detection.

Weekly Report:
- Window: last 7 days.
- Use: governance evidence pack after ritual completion.

Ritual vs Retro:
- KR updates happen in Weekly Ritual step 2.
- RetroBox is review-only for saved retrospectives.

## 8. Dummy Manager UAT Script (Step-by-Step)

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

## 9. Troubleshooting

If manager cannot see team nodes:
1. Verify `manager_id` links on users.
2. Verify there is an active cycle.
3. Verify objectives/KRs are not left in `DRAFT`.
4. Verify manager selected `My Team` (not `My OKRs`) in Atlas scope selector.

If manager can see but cannot edit:
1. Confirm node owner is direct report (manager-of-owner edit rule).
2. Confirm account is active and role is `manager`.
3. Check permission errors in UI and audit logs.
