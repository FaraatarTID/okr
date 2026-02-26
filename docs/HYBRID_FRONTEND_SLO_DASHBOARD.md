Documentation HQ: [README](../README.md)

Hybrid Frontend Cutover SLO Dashboard And Alerting

Date
- 2026-02-25

Purpose
- Define operational SLOs and alert thresholds required by `HFM-060`.
- Standardize dashboard views used for Phase 6 cutover decisions.

Primary source of truth
- SLO contract file: [HYBRID_FRONTEND_SLO_TARGETS.json](HYBRID_FRONTEND_SLO_TARGETS.json)
- Cohort rollout/rollback procedure: [HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md](HYBRID_FRONTEND_COHORT_ROLLOUT_PLAYBOOK.md)

## 1. Required SLO Coverage

The dashboard must include all required user journeys:
- Login success rate (`login_success_rate`)
- Atlas read success and latency (`atlas_read_success_rate`, `atlas_read_p95_latency_ms`)
- Timer mutation success and latency (`timer_mutation_success_rate`, `timer_mutation_p95_latency_ms`)
- Report open success rate (`report_open_success_rate`)

Minimum windows:
- `5m` for fast regression detection.
- `1h` for active rollout gating.
- `24h` for daily checkpoint trend.
- `7d` for cutover readiness.

## 2. Dashboard Layout Contract

Required panels:
1. Success-rate scorecards for login, Atlas read, timer mutation, and report open.
2. P95 latency scorecards for Atlas read and timer mutation.
3. Error-budget burn chart (`1h` and `24h`) for each success-rate SLO.
4. Route-level status distribution (`2xx`, `4xx`, `5xx`) for:
   - `/v1/auth/login`
   - `/v1/read/atlas/snapshot`
   - `/v1/timer/start`
   - `/v1/timer/stop`
5. Correlation panel for quick trace joins:
   - `X-Correlation-ID`
   - `X-Request-ID`

## 3. Alerting Policy

Alert thresholds come from [HYBRID_FRONTEND_SLO_TARGETS.json](HYBRID_FRONTEND_SLO_TARGETS.json).

Routing:
- Warning alerts: team channel (`#okr-oncall`) for active triage.
- Critical alerts: on-call pager + incident channel.

Response objective:
- Begin triage within 5 minutes of critical alert.
- If critical breach persists beyond `for_minutes` and no immediate fix is available, execute scoped or global rollback per playbook.

## 4. Operator Runbook (Triage)

1. Identify affected journey and cohort from dashboard filters.
2. Correlate `spa-web`, `spa-bff`, and backend logs using request/correlation IDs.
3. Classify fault domain:
   - Auth/session
   - BFF proxy/signing
   - Backend authorization/domain
   - Streamlit bridge/report mode mapping
4. Decide action:
   - Hotfix/restart if low-risk and recovery expected within alert window.
   - Rollback cohort to Streamlit-first if risk remains or breach continues.
5. Record incident evidence:
   - Alert timestamps
   - Mitigation action
   - MTTR
   - Follow-up tasks for `HFM-061` and `HFM-062`

## 5. Cutover Gate Usage

Use this dashboard for Phase 6 decisions:
- `HFM-061`: rollback drill validation and MTTR measurement.
- `HFM-062`: two stable weekly cycles at target SLO before final recommendation.

Recorded drill evidence:
- [HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md](HYBRID_FRONTEND_ROLLBACK_DRILL_2026-02-25.md)

Recorded pilot completion review:
- [HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.md](HYBRID_FRONTEND_PILOT_COMPLETION_REVIEW_2026-02-25.md)
