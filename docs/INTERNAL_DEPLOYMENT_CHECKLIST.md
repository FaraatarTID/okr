Documentation HQ: [README](../README.md)

Internal Deployment and Security Checklist

Use this checklist for company-internal pilot rollout sign-off.

Phase 1: Preparation
- [ ] Copy `deploy/secrets/secrets.toml.example` to runtime `secrets.toml` and populate internal values only.
- [ ] Select AI provider (`openai_compatible` recommended for internal gateways, or `gemini` if approved).
- [ ] Keep `ALLOW_EXTERNAL_AI=false` unless outbound AI is explicitly approved.
- [ ] Set `OKR_BACKEND_SERVICE_TOKEN` to a strong shared secret for internal service auth.
- [ ] Review `DEPLOYMENT.md` and `docs/CONFIG_REFERENCE.md`.

Phase 2: Infrastructure
- [ ] Deploy with Docker Compose (or Kubernetes) in a controlled internal environment.
- [ ] Place app behind Nginx/Traefik with TLS termination.
- [ ] Restrict access to company network and/or VPN.
- [ ] Configure PostgreSQL connectivity (internal DB or approved private endpoint).
- [ ] Ensure backend stack is running (`okr`, `backend-api`, `backend-worker`).
- [ ] Ensure `OKR_BACKEND_API_URL` is set in `okr` and `OKR_BACKEND_PROXY_MUTATIONS=true` for backend-owned writes.
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
- [ ] Verify Goal/Objective/KR/Task create-update-delete flows succeed with backend API enabled.
- [ ] Validate PDF/report behavior with `PDF_METHOD=pdfshift` (the only supported runtime mode).
- [ ] Validate backend job flow (`backend-worker` processes AI/PDF requests successfully).
- [ ] Pilot with a limited team and collect feedback.
- [ ] Monitor app and reverse-proxy logs during pilot.

Ongoing Maintenance
- [ ] Update dependencies regularly (CI already enforces lock file + `pip-audit`).
- [ ] Rotate credentials and API keys on a scheduled cadence.
- [ ] Re-validate AI provider/data policy after major infra or vendor changes.
