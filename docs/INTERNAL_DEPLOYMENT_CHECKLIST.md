Documentation HQ: [README](../README.md)

Internal Deployment and Security Checklist

Use this checklist for company-internal pilot rollout sign-off.

Phase 1: Preparation
- [ ] Copy `deploy/secrets/secrets.toml.example` to runtime `secrets.toml` and populate internal values only.
- [ ] Select AI provider (`openai_compatible` recommended for internal gateways, or `gemini` if approved).
- [ ] Set `ALLOW_EXTERNAL_AI=false` if AI must be disabled by policy.
- [ ] Review `DEPLOYMENT.md` and `docs/CONFIG_REFERENCE.md`.

Phase 2: Infrastructure
- [ ] Deploy with Docker Compose (or Kubernetes) in a controlled internal environment.
- [ ] Place app behind Nginx/Traefik with TLS termination.
- [ ] Restrict access to company network and/or VPN.
- [ ] Configure PostgreSQL connectivity (internal DB or approved private endpoint).

Phase 3: Security and Compliance
- [ ] Confirm password policy and admin hardening steps are applied.
- [ ] Confirm AI provider/data flow is approved by security/compliance.
- [ ] Enable database backups and retention policy.
- [ ] Confirm role-based access boundaries (admin/manager/member) in pilot users.
- [ ] Keep all secrets out of git and in approved secret storage.

Phase 4: Testing and Go-Live
- [ ] Run smoke tests: login, OKR creation, timer, dashboard, reports, and AI flows (if enabled).
- [ ] Validate PDF/report behavior for your chosen `PDF_METHOD`.
- [ ] Pilot with a limited team and collect feedback.
- [ ] Monitor app and reverse-proxy logs during pilot.

Ongoing Maintenance
- [ ] Update dependencies regularly (CI already enforces lock file + `pip-audit`).
- [ ] Rotate credentials and API keys on a scheduled cadence.
- [ ] Re-validate AI provider/data policy after major infra or vendor changes.
