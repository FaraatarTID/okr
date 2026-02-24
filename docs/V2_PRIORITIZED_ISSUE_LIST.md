Documentation HQ: [README](../README.md)

V2 Prioritized Issue List (Impact x Effort)

Date
- 2026-02-24

Purpose
- Provide a practical, ranked V2 backlog for security, reliability, and maintainability.
- Keep one implementation-focused list with explicit status (open/in-progress/completed).

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
| V2-01 | P0 | Open | Migrate auth/session to Supabase Auth (GoTrue) | Custom bcrypt auth + local Streamlit session handling are still primary. | H | L | Removes highest long-term security and maintenance risk. |
| V2-02 | P0 | Completed | Add database-backed audit trail (`audit_event` table) | `audit_event` table, structured event sink, and worker-based retention pruning are shipped. | H | M | Compliance and incident evidence now have a durable primary store. |
| V2-03 | P1 | Completed | Make backend read proxy the production default and migrate remaining heavy reads | Backend read/write proxy is enforced in runtime and backend transport failures are fail-closed. | H | M | Architecture split-brain risk is materially reduced. |
| V2-04 | P1 | Completed | Add local PDF renderer mode for air-gapped/privacy-first deployments | Runtime supports `PDF_METHOD=chromium` (local) and `PDF_METHOD=pdfshift` (managed), with preflight validation/tests. | M | M | Sensitive deployments can render PDFs without third-party API dependence. |
| V2-05 | P1 | In Progress | Harden production invariants as startup/release gates | Template config gate + strict runtime preflight exist; release evidence automation can be tightened further. | H | S | Prevents misconfig drift from weakening security posture. |
| V2-06 | P2 | Open | Expand quality gates from targeted checks to broader repo coverage | CI lint/type gates are still targeted to selected modules. | M | M | Reduces regression risk as module count continues to grow. |
| V2-07 | P2 | In Progress | Atlas session-state governance and performance guardrails | Session key constants and rerun telemetry exist; ownership policy + measurable budgets need tighter governance. | M | M | Avoids UI rerun drag and key drift as feature surface expands. |

Execution Order (Remaining Work)

1. V2-01 Auth migration.
2. V2-05 Production invariant gate closure.
3. V2-06 Broader quality gates.
4. V2-07 Session-state governance/perf closure.

Definition of Ready Per Open/In-Progress Item

1. Explicit owner and reviewer assigned.
2. Test plan includes unit + integration coverage updates.
3. Rollout/rollback steps documented in operations docs.
4. Feature flags and production defaults are defined.

Acceptance Criteria (Remaining)

V2-01
- Streamlit login flow delegates identity/session to Supabase Auth.
- Legacy password-hash flow is fully removed or isolated as a dev-only compatibility mode.
- Auth throttle, password reset, and must-change-password flows are revalidated against provider behavior.

V2-05
- Startup/release checks fail when production has unsafe toggles.
- Required backend token/signing settings are validated before go-live.
- Deployment checklist includes evidence steps for each invariant.
- Runtime-mode config validation is executed as part of release governance (not only template checks).

V2-06
- CI adds broader lint/type gates beyond narrowly targeted files.
- Baseline exceptions are explicit and time-boxed.
- New modules are included by default rather than opt-in.

V2-07
- Session keys remain centralized and audited.
- High-frequency rerun paths have measurable budgets and regression tests.
- Atlas key lifecycle policy is documented (set/reset ownership by feature area).

Evidence References
- Custom auth: `streamlit_app/src/crud_auth_helpers.py`
- DB-backed audit trail: `streamlit_app/src/audit.py`, `backend_app/jobs.py`
- Backend read proxy/fail-closed controls: `streamlit_app/src/ui/atlas_runtime_cache_helpers.py`, `streamlit_app/src/crud_core_helpers.py`
- PDF runtime modes (`pdfshift` + `chromium`): `streamlit_app/src/services/pdf_service.py`
- Production invariant checks: `scripts/check_deploy_config.py`, `streamlit_app/src/runtime_preflight.py`
- Rerun telemetry + session key contracts: `streamlit_app/src/ui/app_entry_helpers.py`, `streamlit_app/src/ui/session_keys.py`
- CI gate scope: `.github/workflows/ci.yml`, `.pre-commit-config.yaml`
- Config/runtime controls: `docs/CONFIG_REFERENCE.md`
