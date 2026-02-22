Documentation HQ: [README](../README.md)

Operations guide

First run
- App runs migrations automatically
- Empty DB bootstrap account is `admin`
- Production password source: `OKR_BOOTSTRAP_ADMIN_PASSWORD` (required; minimum 12 chars with upper/lowercase, number, symbol)
- Non-production fallback password: `admin` (local/dev convenience only)
- Initial admin is forced to change password on first login

Backups
- Supabase PostgreSQL: enable automated backups/snapshots and test restore

Monitoring
- Uptime check: GET /
- Backend uptime check: GET /healthz (backend-api)
- Reverse proxy logs (Nginx) for access and errors
- Container logs for `okr`, `backend-api`, and `backend-worker`
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
- Keep backend API port private (`127.0.0.1` bind by default in compose)
- Enable request signing for internal service calls (`OKR_BACKEND_SIGNING_SECRET`)
- Keep `OKR_BACKEND_SECURITY_STATE_BACKEND=database` in production for distributed nonce/rate-limit controls
- Keep `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN` unset/false in production (runtime ignores fail-open overrides in production)
- Keep DB credentials in secret manager and rotate regularly

Incident response
- Take snapshots before risky changes
- Know rollback steps for Compose and K8s
- Prefer pull-based deployment for internal servers; avoid CI-originated SSH access unless explicitly approved.

Runtime preflight checks
- On startup, validate that PDF mode and API keys are coherent.
- If strict mode is enabled and preflight reports errors, treat startup block as configuration incident (not app defect).
- Resolve by fixing provider mismatch:
  - All runtimes: `PDF_METHOD=pdfshift` + `pdfshift_api_key`

Architecture note
- Current MVP uses hybrid execution: read-heavy traversal remains in Streamlit, while backend services own frontend mutation APIs, timer APIs, and async heavy jobs when `OKR_BACKEND_API_URL` is configured.
- Keep `OKR_BACKEND_PROXY_MUTATIONS=1` in internal deployments so frontend write flows route through backend API by default (node CRUD, users/cycles/teams, Learning Loop writes, alignments, work-log deletes).
- Keep `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` unset/false in production so backend failures fail closed.

Release governance
- Protect main branch with required CI checks.
- Required checks:
  - Docs HQ link checker
  - Deploy config template gate
  - RBAC regression gate
  - Full pytest suite
