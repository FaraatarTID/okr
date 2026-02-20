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
- AI provider check:
  - Run `python streamlit_app/scripts/ai_provider_health_check.py`
  - Config-only validation: `python streamlit_app/scripts/ai_provider_health_check.py --no-probe`
  - JSON output for automation: `python streamlit_app/scripts/ai_provider_health_check.py --json`

Upgrades
- Compose: pull new image, up -d --build
- K8s: update image tag, rollout status

Secrets management
- Store DB credentials and API keys in secrets (not in repo)
- Rotate credentials periodically
- For AI features, keep provider credentials only in secrets/env (never in git)
- Set `AI_PROVIDER` explicitly (`gemini` or `openai_compatible`)
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
- On startup, validate that PDF mode and API keys are coherent.
- If strict mode is enabled and preflight reports errors, treat startup block as configuration incident (not app defect).
- Resolve by fixing provider mismatch:
  - All runtimes: `PDF_METHOD=pdfshift` + `pdfshift_api_key`

Release governance
- Protect main branch with required CI checks.
- Required checks:
  - Docs HQ link checker
  - RBAC regression gate
  - Full pytest suite
