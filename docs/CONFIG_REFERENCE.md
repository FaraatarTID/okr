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
    - `postgresql+psycopg2://postgres.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require`
- Streamlit secrets:
  - [database]
    - url: full connection string
  - See template: [deploy/secrets/secrets.toml.example](../deploy/secrets/secrets.toml.example)
- Requirements enforced by runtime:
  - URL must start with `postgresql+psycopg2://`
  - Host must include `*.pooler.supabase.com` (or `*.pooler.supabase.co`)
  - Port must be `6543` (transaction pooler) unless explicitly overridden
  - Optional exception flags:
    - `OKR_ALLOW_SUPABASE_SESSION_POOLER=1` (allow port 5432 on pooler host)
    - `OKR_ALLOW_SUPABASE_DIRECT_CONNECTION=1` (allow non-pooler host)
  - Pool sizing controls:
    - `OKR_DB_POOL_SIZE` (default: `5`)
    - `OKR_DB_MAX_OVERFLOW` (default: `5`)
    - `OKR_DB_POOL_TIMEOUT` (default: `30`)
    - `OKR_DB_POOL_RECYCLE` (default: `1800`)

Streamlit server

- Environment variables:
  - PORT (default 8501)
  - BASE_URL_PATH (empty for subdomain; set to e.g. okr for subpath hosting)
- Streamlit config: [streamlit_app/.streamlit/config.toml](../streamlit_app/.streamlit/config.toml)
  - server.headless=true, enableCORS=true, enableXsrfProtection=true
  - browser.gatherUsageStats=false

PDF generation

- Streamlit secrets keys:
  - PDF_METHOD: pdfshift
  - pdfshift_api_key: required for PDF binary export

AI integration

- Streamlit secrets keys:
  - AI_PROVIDER: `gemini` (default) or `openai_compatible`
  - ALLOW_EXTERNAL_AI: policy gate (`true`/`false`); default `false`
  - GEMINI_API_KEY: required when `AI_PROVIDER=gemini`
  - GEMINI_MODEL: optional override (default: `gemini-flash-latest`)
  - AI_BASE_URL: required when `AI_PROVIDER=openai_compatible`
  - AI_MODEL: required when `AI_PROVIDER=openai_compatible`
  - AI_API_KEY: optional token for OpenAI-compatible gateways
- Environment fallback:
  - AI_PROVIDER
  - OKR_AI_PROVIDER
  - GEMINI_API_KEY
  - VITE_GEMINI_API_KEY
  - GEMINI_MODEL
  - AI_BASE_URL
  - OPENAI_BASE_URL
  - OLLAMA_BASE_URL
  - AI_MODEL
  - OPENAI_MODEL
  - OLLAMA_MODEL
  - AI_API_KEY
  - OPENAI_API_KEY
  - ALLOW_EXTERNAL_AI
  - OKR_ALLOW_EXTERNAL_AI
- Behavior:
  - If `ALLOW_EXTERNAL_AI=false`, outbound AI calls are blocked regardless of provider.
  - `AI_PROVIDER=openai_compatible` uses Chat Completions-style APIs, so self-hosted models can be used without Gemini.
  - Runtime preflight reports this policy as an informational status.

Runtime preflight policy

- Optional strict mode:
  - OKR_STRICT_RUNTIME_PREFLIGHT=1
- Behavior:
  - Runtime validates PDF provider mode and key presence.
  - If strict mode is enabled, critical preflight errors stop app startup.
  - Provider configuration issues are surfaced as warnings/errors depending on severity.

Recommended deployment profiles

- Streamlit Cloud:
  - PDF_METHOD=pdfshift
  - AI_PROVIDER=gemini (or your approved hosted gateway via `openai_compatible`)
  - pdfshift_api_key must be present
  - OKR_STRICT_RUNTIME_PREFLIGHT=1 (recommended)
- Self-hosted server (Docker/VM):
  - PDF_METHOD=pdfshift
  - AI_PROVIDER=openai_compatible for local/self-hosted LLM routing
  - If openai_compatible: set AI_BASE_URL and AI_MODEL
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
