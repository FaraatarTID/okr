Documentation HQ: [README](../README.md)

V2 Prioritized Issue List (Impact x Effort)

Date
- 2026-02-24

Purpose
- Record final V2 closure status for security, reliability, and maintainability work.
- Keep implementation evidence linked to concrete runtime gates and tests.

Scoring
- Impact: H (high), M (medium), L (low)
- Effort: S (small), M (medium), L (large)
- Priority: risk reduction first, then delivery speed.

Status Legend
- Open: not started.
- In Progress: partial controls shipped, remaining closure work defined.
- Completed: acceptance criteria materially met and documented.

Priority Queue

| ID | Priority | Status | Work Item | Current State | Impact | Effort | Why Now |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V2-02 | P0 | Completed | Add database-backed audit trail (`audit_event` table) | `audit_event` table, structured event sink, and worker-based retention pruning are shipped. | H | M | Compliance and incident evidence now have a durable primary store. |
| V2-03 | P1 | Completed | Make backend read proxy the production default and migrate remaining heavy reads | Backend read/write proxy is enforced in runtime and backend transport failures are fail-closed. | H | M | Architecture split-brain risk is materially reduced. |
| V2-04 | P1 | Completed | Add local PDF renderer mode for air-gapped/privacy-first deployments | Runtime supports `PDF_METHOD=chromium` (local) and `PDF_METHOD=pdfshift` (managed), with preflight validation/tests. | M | M | Sensitive deployments can render PDFs without third-party API dependence. |
| V2-05 | P1 | Completed | Harden production invariants as startup/release gates | Template gate + strict runtime preflight + release runtime config gate workflow are now in place. | H | S | Prevents misconfig drift from weakening security posture. |
| V2-06 | P2 | Completed | Expand quality gates from targeted checks to broader repo coverage | CI/pre-commit now run repo-critical Ruff checks, expanded mypy scope (dirs + runtime-core modules), and a time-boxed baseline expiry gate. | M | M | Reduces regression risk as module count continues to grow. |
| V2-07 | P2 | Completed | Atlas session-state governance and performance guardrails | Atlas key lifecycle policy is codified and validated; rerun budget behavior has explicit regression gates. | M | M | Avoids UI rerun drag and key drift as feature surface expands. |

V2 Status

- Closed on 2026-02-24.
- No remaining V2 items.

Evidence References
- DB-backed audit trail: `streamlit_app/src/audit.py`, `backend_app/jobs.py`
- Backend read proxy/fail-closed controls: `streamlit_app/src/ui/atlas_runtime_cache_helpers.py`, `streamlit_app/src/crud_core_helpers.py`
- PDF runtime modes (`pdfshift` + `chromium`): `streamlit_app/src/services/pdf_service.py`
- Production invariant checks: `scripts/check_deploy_config.py`, `streamlit_app/src/runtime_preflight.py`, `.github/workflows/release-runtime-gate.yml`
- Quality gate baseline enforcement: `scripts/check_quality_gate_baseline.py`, `docs/QUALITY_GATE_BASELINE.md`
- Rerun telemetry + session key contracts: `streamlit_app/src/ui/app_entry_helpers.py`, `streamlit_app/src/ui/session_keys.py`, `tests/test_session_keys_policy.py`
- CI gate scope: `.github/workflows/ci.yml`, `.pre-commit-config.yaml`
- Config/runtime controls: `docs/CONFIG_REFERENCE.md`
