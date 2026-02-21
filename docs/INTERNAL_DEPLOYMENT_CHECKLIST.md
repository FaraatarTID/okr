Documentation HQ: [README](../README.md)

Internal Deployment and Security Checklist

Use this checklist for company-internal pilot rollout sign-off.

Phase 1: Preparation
- [ ] Copy `deploy/secrets/secrets.toml.example` to runtime `secrets.toml` and populate internal values only.
- [ ] Validate Streamlit secrets TOML syntax (one key per line, no quoted multi-line blob). Minimal example:
  ```toml
  PDF_METHOD = "pdfshift"
  OKR_BACKEND_PROXY_MUTATIONS = true
  OKR_ALLOW_LOCAL_BACKEND_FALLBACK = false
  OKR_STRICT_RUNTIME_PREFLIGHT = true
  ```
- [ ] Select AI provider (`openai_compatible` recommended for internal gateways, or `gemini` if approved).
- [ ] Keep `ALLOW_EXTERNAL_AI=false` unless outbound AI is explicitly approved.
- [ ] Set `OKR_BACKEND_SERVICE_TOKEN` to a strong shared secret for internal service auth.
- [ ] Set `OKR_BACKEND_SIGNING_SECRET` and keep `OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true`.
- [ ] Review and execute `docs/ACCEPTED_FINDINGS_IMPLEMENTATION_PLAN.md` before production rollout.
- [ ] Review `DEPLOYMENT.md` and `docs/CONFIG_REFERENCE.md`.

Phase 2: Infrastructure
- [ ] Deploy with Docker Compose (or Kubernetes) in a controlled internal environment.
- [ ] Place app behind Nginx/Traefik with TLS termination.
- [ ] Restrict access to company network and/or VPN.
- [ ] Configure PostgreSQL connectivity (internal DB or approved private endpoint).
- [ ] Ensure runtime `OKR_DATABASE_URL` uses least-privilege runtime role credentials (example: `okr_app`, never `postgres`).
- [ ] Treat DB-role verification as a mandatory go-live check even if runtime startup guards are temporarily relaxed.
- [ ] Ensure backend stack is running (`okr`, `backend-api`, `backend-worker`).
- [ ] Ensure `OKR_BACKEND_API_URL` is set in `okr` and `OKR_BACKEND_PROXY_MUTATIONS=true` for backend-owned writes.
- [ ] Ensure `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` is unset/false in production.
- [ ] Confirm reverted behavior is preserved: no direct local mutation fallback in `okr` production runtime.
- [ ] Keep backend API host binding private (`127.0.0.1` unless explicitly required otherwise).

Phase 3: Security and Compliance
- [ ] Confirm password policy and admin hardening steps are applied.
- [ ] Confirm AI provider/data flow is approved by security/compliance.
- [ ] Enable database backups and retention policy.
- [ ] Confirm role-based access boundaries (admin/manager/member) in pilot users.
- [ ] Keep all secrets out of git and in approved secret storage.
- [ ] Confirm internal service boundaries: backend API remains private; only app/proxy endpoints are exposed.

Phase 4: Testing and Go-Live
- [ ] Run smoke tests: login, OKR creation, timer, dashboard, reports, and AI flows (if enabled).
- [ ] Run UI form guard test: `python -m pytest tests/test_streamlit_form_guardrails.py -q` (enforces `st.form_submit_button` usage inside `st.form`).
- [ ] Run auth throttle + login query budget test: `python -m pytest tests/test_auth_rate_limit.py -q` (validates lockout behavior and guards steady-state successful login query count).
- [ ] Run selector integrity guard test: `python -m pytest tests/test_selector_integrity_guardrails.py -q` (enforces ID-backed `selectbox`/`multiselect` options to avoid duplicate-label collisions).
- [ ] Run Atlas cache/latency guard test: `python -m pytest tests/test_atlas_cache_performance.py -q` (enforces deterministic owner-scope cache keys, bounded query budget, and session-level treemap cache reuse on rerun).
- [ ] Run timestamp safety guard test: `python -m pytest tests/test_timestamp_timezone_guardrails.py -q` (enforces centralized UTC epoch conversion helpers).
- [ ] Run UTC API guard test: `python -m pytest tests/test_time_api_guardrails.py -q` (blocks deprecated `datetime.utcnow()` usage in runtime code).
- [ ] Run cycle bootstrap/cache guard test: `python -m pytest tests/test_app_cycle_cache_snapshot.py -q` (verifies cycle selector payload integrity and safe default-cycle bootstrap behavior).
- [ ] Run DB pooling config guard test: `python -m pytest tests/test_database_engine_pooling.py -q` (verifies NullPool defaults, secrets-aware pooling flags, and safe bounds on pool tunables).
- [ ] Run mapper/reload structural guard tests: `python -m pytest tests/test_models_import_consistency.py tests/test_models_relationship_resolution.py tests/test_hot_reload_model_bindings.py tests/test_hot_reload_model_rebinding.py tests/test_no_duplicate_top_level_functions.py -q`.
- [ ] Run model identity + cache invalidation guard tests: `python -m pytest tests/test_model_binding_identity_guard.py tests/test_hot_reload_cache_invalidation.py -q` (ensures hot reload rebinding tracks latest `src.models` classes and clears stale Streamlit data cache).
- [ ] Verify frontend mutation flows succeed with backend API enabled (node CRUD, timer, user/cycle/team admin actions, Learning Loop writes, alignments).
- [ ] Validate PDF/report behavior with `PDF_METHOD=pdfshift` (the only supported runtime mode).
- [ ] Validate backend job flow (`backend-worker` processes AI/PDF requests successfully).
- [ ] Pilot with a limited team and collect feedback.
- [ ] Monitor app and reverse-proxy logs during pilot.

Ongoing Maintenance
- [ ] Update dependencies regularly (CI already enforces lock file + `pip-audit`).
- [ ] Rotate credentials and API keys on a scheduled cadence.
- [ ] Re-validate AI provider/data policy after major infra or vendor changes.
