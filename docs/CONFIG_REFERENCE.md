Configuration reference

Overview
- The app reads configuration from, in order of precedence:
  1) Environment variables
  2) Streamlit secrets (mounted at streamlit_app/.streamlit/secrets.toml)
  3) Defaults inside the app

Production mode
- Environment variable: PRODUCTION=true
- Streamlit secrets:
  [app]
    production = true
- When enabled:
  - Google Sheets sync is disabled
  - SQLite is not allowed; set OKR_DATABASE_URL / DATABASE_URL or [database].url

Database
- Environment variables:
  - OKR_DATABASE_URL (preferred)
  - DATABASE_URL (fallback)
  - Example: postgresql+psycopg2://user:pass@db-host:5432/okr
- Streamlit secrets:
  - [database]
    - url: full connection string (preferred)
    - Or parts to construct: driver, user, password, host, port, name
  - See template: [deploy/secrets/secrets.toml.example](deploy/secrets/secrets.toml.example)
- Default (if unset): SQLite at streamlit_app/okr_database.db

Streamlit server
- Environment variables:
  - PORT (default 8501)
  - BASE_URL_PATH (empty for subdomain; set to e.g. okr for subpath hosting)
- Streamlit config: [streamlit_app/.streamlit/config.toml](streamlit_app/.streamlit/config.toml)
  - server.headless=true, enableCORS=true, enableXsrfProtection=true
  - browser.gatherUsageStats=false

PDF generation
- Streamlit secrets keys:
  - PDF_METHOD: pdfshift or pdfkit (optional override)
  - pdfshift_api_key: required if using pdfshift
- System dependency for pdfkit: wkhtmltopdf (already installed in the container)

Google integration (optional)
- Used only if you want Google Sheets/Drive sync. If omitted, sync is disabled.
- Streamlit secrets keys:
  - gcp_service_account: JSON service account credentials (as TOML map)
  - GCP_SPREADSHEET_NAME: Defaults to OKR_DB if not set

Admin bootstrap
- On first run (empty DB), a default admin user is created:
  - username: admin
  - password: admin
- Change this immediately in the Admin Panel.

Logging & health
- HTTP health check: GET /
- Logs: Streamlit stdout (container logs or service logs)
