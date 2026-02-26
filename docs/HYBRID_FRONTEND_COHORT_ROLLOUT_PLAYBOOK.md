Documentation HQ: [README](../README.md)

Hybrid Frontend Cohort Rollout Playbook

Date
- 2026-02-25

Purpose
- Provide an execution playbook for `HFM-043` (team-by-team SPA rollout).
- Define rollout checkpoints, rollback triggers, and operator actions.

Scope
- Applies to Atlas SPA cohort rollout controlled by:
  - `OKR_SPA_ROLLOUT_ENABLED`
  - `OKR_SPA_ROLLOUT_ALLOW_ALL`
  - `OKR_SPA_ROLLOUT_TEAM_IDS`
  - `OKR_SPA_ROLLOUT_USERNAMES`
  - `OKR_SPA_ROLLOUT_ROLES`
  - `OKR_SPA_ROLLOUT_ALLOW_PREVIEW_BYPASS`
- Unified SPA is the primary and expected runtime for core workflows.

## 1. Roles And Ownership

| Role | Owner | Responsibility |
| --- | --- | --- |
| Rollout Commander | Engineering lead | Approves wave start/stop and rollback decisions. |
| On-call Operator | Platform/on-call | Applies env changes and restarts `spa-web`. |
| Product/UX Observer | Pilot product owner | Collects pilot usability feedback and blockers. |
| Security Reviewer | Security/platform reviewer | Confirms no auth or boundary regressions. |

## 2. Wave Plan

| Wave | Cohort | Duration | Entry Rule | Exit Rule |
| --- | --- | --- | --- | --- |
| Wave 0 | Internal admins only (`roles=admin`) | 1 day | HFM-042 parity checks green in target env. | No critical auth/security regressions for one business day. |
| Wave 1 | 1-2 pilot teams (`team_ids`) | 2-3 days | Wave 0 stable. | Error and latency checkpoints pass for two consecutive business days. |
| Wave 2 | 25-50% pilot scope (`team_ids` + optional `usernames`) | 3-5 days | Wave 1 stable. | No rollback-trigger incidents for one full weekly check-in cycle. |
| Wave 3 | Default pilot mode (`allow_all=true` for pilot env) | 1-2 weeks | Wave 2 stable. | Inputs ready for HFM-060 SLO dashboard and cutover review. |

## 3. Change Procedure Per Wave

1. Prepare `.env` rollout keys for target cohort.
2. Apply configuration and restart `spa-web` in deployment environment.
3. Validate rollout config endpoint:
   - `GET /api/rollout` must return expected `enabled`, cohort lists, and fallback URL.
4. Run smoke actions with a cohort user:
   - login
   - Atlas snapshot read
   - timer start/stop
   - node create/update/delete
5. Announce wave start in team channel with rollback path.

## 4. Monitoring Checkpoints

Run checkpoints at `T+15m`, `T+60m`, and end-of-day for each wave.

Minimum health checks:
- `spa-web` route health and render availability.
- `spa-bff` logs: upstream status distribution for `/v1/read/atlas/snapshot`, `/v1/timer/*`, `/v1/nodes/*`.
- Backend logs: authorization errors (`403`) and unexpected `5xx` spikes.
- Pilot user report: receives expected cohort policy outcome (allowed vs excluded) without auth leakage.

Cutover thresholds (source of truth: `docs/HYBRID_FRONTEND_SLO_TARGETS.json`):
- Login success >= 99%.
- Atlas snapshot read success >= 99%.
- Timer mutation success >= 99%.
- Report open success >= 99%.
- Atlas snapshot read p95 latency <= 1200 ms.
- Timer mutation p95 latency <= 1500 ms.
- Node CRUD mutation success >= 98% (operational checkpoint, not cutover SLO).
- No sustained `5xx` burst for 10+ minutes on SPA/BFF/backend mutation paths.

## 5. Rollback Triggers

Trigger immediate rollback of SPA cohort policy for affected cohort if any condition occurs:

1. Security/auth regression:
- Unauthorized data access, actor propagation break, or signing/boundary failure.
2. Availability regression:
- Sustained `5xx` errors breach checkpoint thresholds.
3. Functional regression:
- Timer or node mutation flows fail repeatedly for pilot users.
4. Data integrity risk:
- Mutation results diverge from backend source of truth.

## 6. Rollback Actions

Global rollback (all SPA cohorts):
1. Set `OKR_SPA_ROLLOUT_ENABLED=false`.
2. Restart `spa-web`.
3. Verify `GET /api/rollout` returns `enabled=false`.
4. Confirm excluded users are denied SPA cohort access as expected.

Scoped rollback (single team/user cohort):
1. Remove affected `team_ids`/`usernames` from rollout keys.
2. Restart `spa-web`.
3. Validate cohort exclusion with `GET /api/rollout` and user login test.

Target rollback completion objective:
- Cohort policy rollback completed in less than 15 minutes.

## 7. Communication Templates

Wave start:
- "SPA rollout wave <N> started for cohort <X>. Report issues in <channel>."

Rollback event:
- "SPA rollout wave <N> rolled back for cohort <X> at <time>. Cohort is now excluded while incident triage continues."

## 8. Evidence To Record Per Wave

- Timestamped `.env` change record for rollout keys.
- `GET /api/rollout` response snapshot after change.
- Checkpoint notes for `T+15m`, `T+60m`, end-of-day.
- Incident/rollback notes if triggered (reason, time-to-rollback, gaps).

Exit
- This playbook satisfies `HFM-043` procedural requirement.
- Quantitative SLO instrumentation is tracked separately in `HFM-060`.

