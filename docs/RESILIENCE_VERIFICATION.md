Documentation HQ: [README](../README.md)

Resilience Verification

Purpose

- This runbook verifies the distributed resilience work from the implementation plan:
  1. Cache invalidation signal is shared across nodes.
  2. URL-backed navigation state survives rerun/refresh/failover.
  3. Multi-instance behavior is operationally testable before release.

Current implementation status (2026-02-24)

- Verification tooling is implemented:
  - `scripts/verify_resilience.py`
  - `scripts/run_multi_instance_failover_drill.py`
- The implementation-plan resilience controls are in place and testable.

Automated Checks

- Run the resilience pytest subset:
  - `python scripts/verify_resilience.py`
- Optional: include extra pytest flags (repeatable):
  - `python scripts/verify_resilience.py --extra-pytest-arg=-k --extra-pytest-arg=query`
- Run a local multi-instance failover harness (backend + Streamlit A/B):
  - `python scripts/run_multi_instance_failover_drill.py`

Live Backend State Checks

- These checks exercise `/v1/state/{key}` and distributed invalidation signaling through real backend auth/signing policy.
- Run:
  - `python scripts/verify_resilience.py --live-backend-check --actor system`
- To fail hard when backend is not reachable/configured:
  - `python scripts/verify_resilience.py --live-backend-check --require-live-backend --actor system`

Expected live prerequisites:

- `OKR_BACKEND_API_URL` is set (for example `http://127.0.0.1:8100`)
- `OKR_BACKEND_SERVICE_TOKEN` matches backend configuration
- If request signing is enforced:
  - `OKR_BACKEND_SIGNING_SECRET` matches backend configuration

Multi-Instance Drill (Manual)

You can run an infrastructure-level automated harness first:

- `python scripts/run_multi_instance_failover_drill.py`
- This validates:
  - backend + dual Streamlit readiness
  - distributed invalidation signal propagation
  - same URL accessibility on replica B after stopping replica A
- It does not assert visual UI pointer restoration semantics; keep the manual checklist below as final release evidence.

1. Start backend API (`8100`) and two Streamlit instances against the same backend/database.
   - Instance A: `streamlit run streamlit_app/app.py --server.port 8501`
   - Instance B: `streamlit run streamlit_app/app.py --server.port 8502`
2. Authenticate as the same user on both instances.
3. On Instance A, perform a mutation that clears cache (for example create/update task or KR).
4. On Instance B, trigger a rerun (sidebar click or page interaction) and verify updated data appears immediately.
   - Pass criteria: no waiting for the old 60-second cache TTL.
5. On Instance A, navigate to a focused context (cycle + report mode + selected node/focus task).
6. Copy the full URL (including query params), then stop Instance A process.
7. Open Instance B (or another replica) with the same URL and re-authenticate if required.
8. Verify context restoration:
   - Cycle selector restored.
   - Dialog/report mode restored.
   - Inspector/timer/focus pointer and nav context restored when valid.

Release Gate Recommendation

- Mark resilience verification as passing only when both are true:
  1. `python scripts/verify_resilience.py` passes.
  2. Multi-instance manual drill passes in your target deployment shape.
