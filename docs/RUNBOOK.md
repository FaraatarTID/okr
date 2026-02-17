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
  - Streamlit Cloud: `PDF_METHOD=pdfshift` + `pdfshift_api_key`
  - Self-hosted server: `PDF_METHOD=pdfkit` + installed `wkhtmltopdf` (or use pdfshift by policy)
- Configure `GEMINI_API_KEY` if AI features are enabled
- Enable strict runtime checks in production: `OKR_STRICT_RUNTIME_PREFLIGHT=1`

4) Start services
- Compose: start app
- K8s: apply manifests

5) Post-deploy checks
- Health check: GET /
- Login as admin/admin and change password
- Create your first cycle and users
- Confirm runtime preflight has no critical errors
- Verify one PDF export succeeds in the selected provider mode
- Verify one AI action succeeds (or document AI as intentionally disabled)

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
