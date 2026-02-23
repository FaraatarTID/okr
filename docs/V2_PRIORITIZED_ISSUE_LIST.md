Documentation HQ: [README](../README.md)

V2 Prioritized Issue List (Impact x Effort)

Date
- 2026-02-23

Purpose
- Provide a practical, ranked V2 backlog for security, reliability, and maintainability.
- Replace legacy planning docs with one maintained, implementation-focused backlog.

Scoring
- Impact: H (high), M (medium), L (low)
- Effort: S (small), M (medium), L (large)
- Priority is based on risk reduction first, then delivery speed.

Priority Queue

| ID | Priority | Work Item | Current State | Impact | Effort | Why Now |
| --- | --- | --- | --- | --- | --- | --- |
| V2-01 | P0 | Migrate auth/session to Supabase Auth (GoTrue) | Custom bcrypt auth + local session handling | H | L | Removes highest long-term security and maintenance risk. |
| V2-02 | P0 | Add database-backed audit trail (`audit_event` table) | `audit_event` table + dual-write sink + worker-based retention pruning shipped | H | M | Enables reliable querying, retention, and compliance evidence. |
| V2-03 | P1 | Make backend read proxy the production default and migrate remaining heavy reads | Backend read proxy exists but is optional | H | M | Reduces architecture split-brain and eases future non-Streamlit clients. |
| V2-04 | P1 | Add local PDF renderer mode for air-gapped/privacy-first deployments | Runtime supports `pdfshift` binary path only | M | M | Removes third-party dependency for sensitive internal exports. |
| V2-05 | P1 | Harden production invariants as startup/release gates | Many controls exist, but gate enforcement can be tightened | H | S | Prevents misconfig drift from weakening security posture. |
| V2-06 | P2 | Expand quality gates from targeted checks to broader repo coverage | Pre-commit lint/type checks are currently targeted | M | M | Reduces regression risk as module count continues to grow. |
| V2-07 | P2 | Atlas session-state governance and performance guardrails | Session state is extensive and distributed across helpers | M | M | Avoids UI rerun drag and key drift as feature surface expands. |

Execution Order (Recommended)

1. V2-01 Auth migration.
2. V2-02 Database audit trail.
3. V2-05 Production invariant gates.
4. V2-03 Backend read proxy default + read migrations.
5. V2-04 Local PDF renderer option.
6. V2-06 Broader quality gates.
7. V2-07 Session-state governance/perf.

Definition of Ready Per Item

1. Explicit owner and reviewer assigned.
2. Test plan includes unit + integration coverage updates.
3. Rollout/rollback steps documented in operations docs.
4. Feature flags and production defaults are defined.

Acceptance Criteria (Concise)

V2-01
- Streamlit login flow delegates identity/session to Supabase Auth.
- Legacy password-hash flow is fully removed or isolated as a dev-only compatibility mode.
- Auth throttle, password reset, and must-change-password flows are revalidated against provider behavior.

V2-02
- `audit_event` table stores actor/action/entity/time/result fields.
- Critical admin and mutation paths emit structured events.
- Retention and query examples are documented for incident response.

V2-03
- `OKR_BACKEND_PROXY_READS=true` is standard production profile.
- Top read-heavy paths are backend-served with contract tests.
- Local read fallback behavior remains explicitly policy-controlled.

V2-04
- Introduce a local renderer mode (for example `weasyprint`) with runtime preflight checks.
- Keep current `pdfshift` mode for managed deployments.
- Export tests cover both configured modes.

V2-05
- Startup/release checks fail when production has unsafe toggles.
- Required backend token/signing settings are validated before go-live.
- Deployment checklist includes evidence steps for each invariant.

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
- Current audit logging: `streamlit_app/src/audit.py`
- Backend read fallback/proxy controls: `streamlit_app/src/ui/atlas_runtime_cache_helpers.py`
- PDF runtime mode: `streamlit_app/src/services/pdf_service.py`
- Targeted quality hooks: `.pre-commit-config.yaml`
- Config/runtime controls: `docs/CONFIG_REFERENCE.md`
