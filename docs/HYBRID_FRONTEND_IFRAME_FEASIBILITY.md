Documentation HQ: [README](../README.md)

Hybrid Frontend Iframe Feasibility Assessment

Date
- 2026-02-25

Purpose
- Evaluate optional iframe-based Streamlit embedding for `HFM-051`.
- Record a clear `adopt` or `reject` decision for current migration phase.

Decision
- `reject` for current phase.

Summary
- Keep report and workflow surfaces native in SPA runtime.
- Do not embed Streamlit reports inside SPA via iframe at this stage.

## Evidence Reviewed

1. Reverse proxy behavior is currently Streamlit-root oriented:
- `deploy/nginx.okr.mycompany.com.conf` routes `location /` to Streamlit upstream.
- Websocket upgrade headers are explicitly tuned for Streamlit interaction paths.

2. Frame policy is only partially aligned with iframe rollout:
- `deploy/nginx.okr.mycompany.com.conf` sets `X-Frame-Options SAMEORIGIN`.
- This allows same-origin framing but does not by itself solve cross-service auth/session coupling.

3. Deployment topology separates SPA and Streamlit services:
- `deploy/docker/docker-compose.yml` runs SPA services by default and keeps `okr` (Streamlit) behind `legacy-streamlit` profile.
- Current migration direction is unified SPA for core operator-facing workflows.

## Assessment Matrix

| Dimension | Current State | Risk | Result |
| --- | --- | --- | --- |
| CSP / Frame headers | `SAMEORIGIN` present in one nginx template; no unified CSP profile for iframe embedding | Medium | Not enough for production embedding policy. |
| Session/auth continuity | SPA and Streamlit are separate runtimes with independent session handling | High | Embedding could create confusing re-auth and partial context behavior. |
| Operational complexity | Requires coordinated proxy paths, websocket stability, and frame policy alignment across environments | Medium | Additional rollout burden with limited near-term value. |
| User value vs native SPA | Native SPA already provides core report/check-in/admin access with lower coupling | Low | Iframe does not justify current complexity cost. |

## Exit Criteria To Reconsider

Re-open iframe option only when all are true:
1. Unified ingress contract defines stable same-origin paths for both SPA and Streamlit.
2. Explicit CSP and frame-ancestor policy is documented and enforced in all production templates.
3. Session continuity expectations are validated with staging e2e coverage for embedded reports.
4. Support burden from redirect bridge is proven insufficient for pilot cohorts.

## Migration Alignment

- This decision closes `HFM-051` with `reject`.
- Phase continues with redirect bridge for report access (`HFM-050`) and moves to SLO/cutover work (`HFM-060+`).
