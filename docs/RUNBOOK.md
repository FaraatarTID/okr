Documentation HQ: [README](../README.md)

Runbook: first deployment

1) Build and publish image (optional if using local build)
- Use the provided GitHub Actions workflow or build locally.

2) Choose deployment path
- Docker Compose on a single VM (recommended to start)
- Kubernetes in a cluster (optional)

3) Configure environment
- Provide OKR_DATABASE_URL for Supabase PostgreSQL (required)
- Decide hosting scheme: subdomain vs subpath
- Configure reverse proxy with TLS and websocket support
- Configure PDF mode explicitly:
  - All runtimes: `PDF_METHOD=pdfshift` + `pdfshift_api_key`
- Configure backend routing:
  - `OKR_BACKEND_API_URL` (default in compose: `http://backend-api:8100`)
  - `OKR_BACKEND_SERVICE_TOKEN` (strong shared secret)
  - `OKR_BACKEND_SIGNING_SECRET` (recommended; signed internal requests)
  - `OKR_BACKEND_PROXY_MUTATIONS=true` (recommended)
  - keep `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` unset/false in production
- Configure `GEMINI_API_KEY` if AI features are enabled
- Enable strict runtime checks in production: `OKR_STRICT_RUNTIME_PREFLIGHT=1`

4) Start services
- Compose: start `okr`, `backend-api`, and `backend-worker`
- K8s: apply manifests

5) Post-deploy checks
- Health check: GET /
- Backend health check: GET /healthz on backend-api
- Login as admin/admin and change password
- Create your first cycle and users
- Confirm runtime preflight has no critical errors
- Verify one PDF export succeeds in the selected provider mode
- Verify one AI action succeeds (or document AI as intentionally disabled)
- Verify async job path works end-to-end (submit AI/PDF action and confirm worker completion)
- Verify Goal/Objective/KR/Task create-update-delete works with backend API enabled
- Run AI provider health check:
  - `python streamlit_app/scripts/ai_provider_health_check.py`

6) Enable optional integrations
- Add secrets.toml for PDFShift or Gemini if required

7) Set up backups and monitoring
- Automated DB backups
- Uptime checks on the proxy endpoint
- Log retention for proxy and app

8) Protect release flow
- Enable branch protection on main branch
- Require passing CI checks before merge:
  - Docs HQ Link Check
  - RBAC Regression Gate
  - Full tests
