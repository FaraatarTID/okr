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

Admin bootstrap

- On first run (empty DB), a default admin user is created:
  - username: admin
  - password: admin
- Change this immediately in the Admin Panel.

Logging & health

- HTTP health check: GET /
- Logs: Streamlit stdout (container logs or service logs)
