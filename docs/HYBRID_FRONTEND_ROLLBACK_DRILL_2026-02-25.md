Documentation HQ: [README](../README.md)

Hybrid Frontend Rollback Drill Record

Date
- 2026-02-25

Backlog mapping
- Work item: `HFM-061`
- Dependency: `HFM-060` completed SLO dashboard/threshold contract

Source record
- Machine-readable drill evidence: [HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.json](HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.json)
- Rollback procedure baseline: [HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md](HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md)

## 1. Drill Objective

Validate scoped cohort rollback from SPA-first to Streamlit-first in less than 15 minutes when a critical SLO breach is detected.

## 2. Drill Setup

- Environment: `staging-production-safe`
- Scope mode: `scoped` (`team_ids=["pilot-team-a"]`, `usernames=["pilot_manager_a"]`)
- Synthetic trigger: critical alert on `timer_mutation_success_rate`
- Trigger details: simulated sustained `5xx` burst on `/v1/timer/start` and `/v1/timer/stop`

## 3. Timeline (UTC)

| Event | Timestamp |
| --- | --- |
| Incident declared | 2026-02-25T16:10:00Z |
| Rollback started | 2026-02-25T16:11:00Z |
| Rollback completed | 2026-02-25T16:18:00Z |

Measured MTTR:
- `8` minutes from incident declaration to rollback completion.
- Objective met (`<15` minutes).

## 4. Actions Executed

1. Set `OKR_SPA_ROLLOUT_ENABLED=false`.
2. Restarted `spa-web`.
3. Verified `GET /api/rollout` returned `enabled=false`.
4. Verified pilot user hit expected rollback policy behavior for excluded cohort scope.

## 5. Verification Evidence

- `spa-web` health endpoint remained available after restart.
- Rollout endpoint reflected disabled SPA policy for scope.
- Pilot user experienced expected excluded-cohort behavior during rollback window.
- Synthetic timer-mutation critical alert condition cleared after rollback.

## 6. Gaps Identified

1. `gap-001` (medium): incident channel announcement was delayed by 4 minutes.
2. `gap-002` (low): rollout endpoint evidence capture is still manual.

## 7. Follow-Up Actions

1. Add automated rollback evidence capture for `GET /api/rollout`.
2. Add a prefilled pager handoff template to speed communication during rollback.

Exit
- This drill satisfies `HFM-061` acceptance criteria: staged rollback drill documented with MTTR and identified gaps.
