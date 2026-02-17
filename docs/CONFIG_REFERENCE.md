Documentation HQ: [README](../README.md)

Configuration reference

Overview

- The app reads configuration from, in order of precedence:
  1. Environment variables
  2. Streamlit secrets (mounted at streamlit_app/.streamlit/secrets.toml)

Database

- Environment variables:
  - OKR_DATABASE_URL (recommended)
  - DATABASE_URL (optional alias)
  - Example:
    - `postgresql+psycopg2://postgres.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require`
- Streamlit secrets:
  - [database]
    - url: full connection string
  - See template: [deploy/secrets/secrets.toml.example](../deploy/secrets/secrets.toml.example)
- Requirements enforced by runtime:
  - URL must start with `postgresql+psycopg2://`
  - Host must include `supabase.com`

Streamlit server

- Environment variables:
  - PORT (default 8501)
  - BASE_URL_PATH (empty for subdomain; set to e.g. okr for subpath hosting)
- Streamlit config: [streamlit_app/.streamlit/config.toml](../streamlit_app/.streamlit/config.toml)
  - server.headless=true, enableCORS=true, enableXsrfProtection=true
  - browser.gatherUsageStats=false

PDF generation

- Streamlit secrets keys:
  - PDF_METHOD: pdfshift or pdfkit (optional override)
  - pdfshift_api_key: required if using pdfshift
- System dependency for pdfkit: wkhtmltopdf (already installed in the container)

AI integration

- Streamlit secrets keys:
  - GEMINI_API_KEY: required for AI analysis and coaching features
- Environment fallback:
  - GEMINI_API_KEY
  - VITE_GEMINI_API_KEY

Runtime preflight policy

- Optional strict mode:
  - OKR_STRICT_RUNTIME_PREFLIGHT=1
- Behavior:
  - Runtime validates PDF provider mode and key/dependency presence.
  - If strict mode is enabled, critical preflight errors stop app startup.
  - Non-critical issues (for example missing wkhtmltopdf in pdfkit mode) are surfaced as warnings.

Recommended deployment profiles

- Streamlit Cloud:
  - PDF_METHOD=pdfshift
  - pdfshift_api_key must be present
  - OKR_STRICT_RUNTIME_PREFLIGHT=1 (recommended)
- Self-hosted server (Docker/VM):
  - PDF_METHOD=pdfkit (or pdfshift if desired)
  - If pdfkit: wkhtmltopdf must be installed and reachable
  - OKR_STRICT_RUNTIME_PREFLIGHT=1 (recommended)

Release governance (CI)

- Branches should require passing CI checks before merge:
  - Docs HQ link check
  - RBAC regression gate
  - Full pytest suite

Admin bootstrap

- On first run (empty DB), a default admin user is created:
  - username: admin
  - password: admin
- Change this immediately in the Admin Panel.

Logging & health

- HTTP health check: GET /
- Logs: Streamlit stdout (container logs or service logs)
