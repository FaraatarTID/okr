Documentation HQ: [README](../README.md)

Operations guide

First run
- App runs migrations automatically
- Default admin admin/admin is created; change password immediately

Backups
- Supabase PostgreSQL: enable automated backups/snapshots and test restore

Monitoring
- Uptime check: GET /
- Reverse proxy logs (Nginx) for access and errors
- Container logs for app messages

Upgrades
- Compose: pull new image, up -d --build
- K8s: update image tag, rollout status

Secrets management
- Store DB credentials and API keys in secrets (not in repo)
- Rotate credentials periodically
- For AI features, keep `GEMINI_API_KEY` only in secrets/env (never in git)
- Set PDF provider mode explicitly with `PDF_METHOD` and matching dependencies/keys
- Recommended in production: `OKR_STRICT_RUNTIME_PREFLIGHT=1`

Security hardening
- TLS everywhere
- Limit exposed ports (only proxy exposed)
- Non-root containers (already configured)
- Set firewall rules so only the proxy can reach the app port
- Keep DB credentials in secret manager and rotate regularly

Incident response
- Take snapshots before risky changes
- Know rollback steps for Compose and K8s

Runtime preflight checks
- On startup, validate that PDF mode and dependencies/keys are coherent.
- If strict mode is enabled and preflight reports errors, treat startup block as configuration incident (not app defect).
- Resolve by fixing provider mismatch:
  - Cloud: `PDF_METHOD=pdfshift` + `pdfshift_api_key`
  - Self-hosted + pdfkit: ensure `wkhtmltopdf` is present

Release governance
- Protect main branch with required CI checks.
- Required checks:
  - Docs HQ link checker
  - RBAC regression gate
  - Full pytest suite
