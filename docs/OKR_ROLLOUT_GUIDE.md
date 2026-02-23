# OKR Rollout Guide (Enterprise)
Documentation HQ: [README](../README.md)

This guide translates enterprise OKR rollout practices into an execution model for this project.
It complements:
- `docs/OKR_LIFECYCLE_GUIDE.md` (state machine + lifecycle constraints)
- `docs/MANAGER_PLAYBOOK.md` (manager operating rhythm)
- `docs/USER_GUIDE.md` (daily user workflow)
- Persian counterpart: `docs/OKR_ROLLOUT_GUIDE_FA.md`

Use this document when you are introducing OKRs across multiple teams or business units, not only running one team cycle.

## 1. Rollout Goal: Choose the Transformation Type

Decide and document the target model before rollout starts:
- `Fully agile`: broad OKR adoption where market conditions are volatile and cross-team adaptation is critical.
- `Mixed approach`: OKRs in change-heavy areas while predictable areas stay on existing planning methods, but still align to shared strategic outcomes.

Why this matters:
- Pilot design, training depth, role setup, and scaling sequence are different for each target model.

## 2. Prerequisite Gate (Before Pilot Launch)

Confirm the organization and system are ready:

| Gate | What "ready" means in practice |
|---|---|
| Openness and transparency | Teams are informed that OKRs change planning behavior, not only reporting format. |
| Strategy clarity | Vision/mission and strategic priorities are explicit enough to derive cycle Objectives. |
| Culture | Mistakes are treated as learning signals; retrospectives are safe to run honestly. |
| Performance assessment boundary | OKRs are not used as direct individual performance rating tools. |
| Leadership style | Sponsors and managers are prepared to coach and remove blockers, not only control output. |
| Platform readiness | Roles, cycle, and scope visibility are correctly configured in the app (`admin/manager/member`, `manager_id`, active cycle). |

If any gate is missing, pause rollout and close that gap first.

## 3. Pilot Design Parameters

Use the following defaults unless there is a strong reason to deviate:

| Parameter | Recommended baseline |
|---|---|
| Pilot group size | Start with 100-250 employees. |
| Pilot duration | At least 2 full cycles (typically 6-8 months total). |
| Preparation lead time | 1-2 months before first active cycle. |
| Team selection | Prefer units with agility affinity, manageable external dependencies, and supportive leadership. |
| Success metric model | Use KR scoring scale `0.0-1.0` and define rollout KPIs before cycle start. |
| Tooling | Manage OKRs centrally in one system and avoid fragmented tracking. |
| Meetings | Pre-schedule planning, weekly check-ins, review, and retrospective for the whole cycle. |
| Communication | Run an explicit rollout communication stream from day 0. |

## 4. Eight-Step Pilot Execution Model

| Step | Outcome artifact | Owner |
|---|---|---|
| 1. Set a clear goal | Written transformation charter (`fully agile` or `mixed`) | Executive sponsor + project lead |
| 2. Define scope/parameters | Pilot brief with size, duration, KPIs, meetings, tooling | Project lead |
| 3. Select pilot group | Named participant list across hierarchy levels/functions | Project lead + managers |
| 4. Assign key roles | Role map: sponsor, project lead, HR/People lead, OKR coach(es) | Sponsor |
| 5. Deliver coaching | Role-specific training plan + completion log | HR/People lead + OKR coaches |
| 6. Run first cycle | Cycle plan, weekly check-ins, review outcomes | Managers + OKR coaches |
| 7. Reflect on pilot | Retrospective output + participant survey results | Project lead + OKR coaches |
| 8. Plan rollout | Scaling decision, next-wave teams, change plan | Sponsor + project lead |

## 5. Ceremony Operating Model in This Product

Map rollout ceremonies to product workflows:
- `OKR Planning`: create/align Objectives/KRs, move from `DRAFT` to `ACTIVE` when execution starts.
- `Weekly`: run Weekly Ritual, especially Step 2 (`Update KRs`) for check-in discipline.
- `Review`: evaluate cycle outcomes with Strategic Dashboard + reports.
- `Retrospective`: capture reflection signals, review RetroBox evidence, define process improvements.

Execution rule:
- Schedule all recurring ceremonies before cycle start and treat them as non-optional governance events.

## 6. Pilot Success Criteria (Define Up Front)

Set explicit pass/fail thresholds before the first cycle. Recommended categories:
- Adoption: participation in planning, weekly ritual completion, training coverage.
- Quality: KR clarity, metric quality, confidence trends, variation discipline.
- Execution: check-in freshness, overdue risk trend, at-risk KR trend.
- Alignment: visibility of priorities and cross-team dependency clarity.
- Learning: retrospective quality and number of actionable improvements carried to next cycle.

Decision rule:
- Do not scale based only on enthusiasm; scale only after evidence from at least two cycles.

## 7. Scaling Models

### Bottom-up scaling
- Start from a pilot team and expand horizontally to neighboring teams, then up hierarchy.
- Strength: organic adoption and local learning.
- Risk: weak leadership linkage can block systemic obstacles.

### Top-down scaling
- Start from leadership strategy layer and cascade through value streams.
- Strength: strategic clarity and executive sponsorship.
- Risk: rollout can stall at upper layers without team-level ownership.

### Mixed scaling (recommended for this guide)
- Combine top-down strategic framing with bottom-up execution learning.
- Strength: strategic coherence plus practical adoption.
- Risk: higher change-management complexity, especially at boundaries with non-OKR areas.

## 8. Team Readiness Scorecard for Next-Wave Selection

Before adding new teams, assess:
- Are team members willing to own strategic outcomes (not just tasks)?
- Can the team make local decisions without excessive approval latency?
- Are managers willing and able to coach through weekly OKR events?

Select expansion teams using readiness evidence, not org-chart convenience.

## 9. Resource and Knowledge Design

For large organizations:
- Pool learnings centrally so pilot teams do not reinvent practices in parallel.
- Keep templates, FAQs, role playbooks, and examples in one discoverable location.
- Convert pilot participants into ambassadors/champions for future waves.

In this repository, keep rollout assets discoverable from `README.md` and link role-specific guides directly.

## 10. Role Model and Accountability

Minimum role structure:
- `OKR Executive Sponsor`: strategic sponsorship, decision support, resource commitment.
- `OKR Project Lead`: end-to-end rollout ownership.
- `OKR HR/People Lead`: training and people-process alignment.
- `OKR Coach/Master`: method expertise, facilitation, quality coaching.

Implementation note:
- One coach can support multiple teams; capacity and quality must be monitored to avoid overload.

## 11. Suggested Timeline (Two-Cycle Baseline)

1. `T-8 to T-4 weeks`: define target model, pilot scope, roles, communication plan.
2. `T-4 to T-1 weeks`: run training, prepare OKR drafts, lock ceremony calendar.
3. `Cycle 1`: execute planning, weeklys, review, retrospective; collect evidence.
4. `Cycle 2`: apply improvements from cycle 1 and re-measure.
5. `Post-cycle 2`: decide scaling path and launch next-wave teams.

## 12. Failure Patterns and Countermeasures

| Failure pattern | Countermeasure |
|---|---|
| Treating OKRs as KPI-only reporting | Re-anchor on objectives, initiatives, and weekly learning loop. |
| Skipping retrospectives or making them ceremonial only | Use structured agenda (`Start/Stop/Continue`) and track carry-over actions. |
| Expanding too quickly after one positive cycle | Enforce two-cycle evidence minimum before major scale-out. |
| Tool fragmentation across teams | Use one central source of truth for goals, check-ins, and rollup views. |
| Manager role reduced to status policing | Shift manager rhythm toward coaching, blocker removal, and quality feedback. |

## 13. Implementation Crosswalk in This Repo

- Lifecycle constraints and transitions: `docs/OKR_LIFECYCLE_GUIDE.md`
- Manager coaching and governance rhythm: `docs/MANAGER_PLAYBOOK.md`
- User execution behavior and ritual flow: `docs/USER_GUIDE.md`
- Learning-loop mechanics for check-in quality: `docs/learning-loop.md`

Use this guide as the rollout governance layer above those implementation-specific guides.

## 14. Ready-to-Use Templates

Use these templates to operationalize rollout decisions:
- `docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE.md`
- `docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST.md`
- `docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE.md`

Persian counterparts:
- `docs/templates/OKR_ROLLOUT_CHARTER_TEMPLATE_FA.md`
- `docs/templates/OKR_ROLLOUT_READINESS_CHECKLIST_FA.md`
- `docs/templates/OKR_PILOT_RETRO_SURVEY_TEMPLATE_FA.md`
