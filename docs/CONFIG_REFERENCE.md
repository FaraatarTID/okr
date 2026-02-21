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
    - `postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require`
- Streamlit secrets:
  - root keys:
    - `OKR_DATABASE_URL` (supported)
    - `DATABASE_URL` (supported alias)
  - [database]
    - url: full connection string
  - See template: [deploy/secrets/secrets.toml.example](../deploy/secrets/secrets.toml.example)
- Runtime validation behavior:
  - URL must start with `postgresql+psycopg2://` (or `sqlite:///` for local/test only).
  - PostgreSQL URLs must include a host.
- Runtime DB URL strictness flags:
  - `OKR_ALLOW_NON_SUPABASE_DB` (default: `1`)
    - `1`: relaxed compatibility mode (permits non-Supabase/non-pooler URLs; startup guards are softer).
    - `0`: strict Supabase validation mode (enforces pooler/role checks below).
  - `OKR_ALLOW_SUPABASE_SESSION_POOLER` (default: `0`)
    - Only relevant when strict mode is enabled.
    - `1` allows Supabase session pooler on `:5432`; otherwise runtime expects transaction pooler `:6543`.
  - `OKR_ALLOW_SUPABASE_DIRECT_CONNECTION` (default: `0`)
    - Only relevant when strict mode is enabled.
    - `1` allows direct/non-pooler Supabase hosts.
  - `OKR_ALLOW_SUPABASE_SUPERUSER` (default: `0`)
    - Only relevant when strict mode is enabled.
    - `1` permits `postgres*` usernames in DSN (not recommended for production).
- Production requirements (deployment policy, mandatory):
  - Enforce strict runtime DB validation with `OKR_ALLOW_NON_SUPABASE_DB=0`.
  - Use Supabase transaction pooler (`*.pooler.supabase.com:6543`) with `sslmode=require`.
  - Use a dedicated least-privilege runtime DB user (example: `okr_app`, typically `okr_app.<project_ref>` in Supabase pooler DSN).
  - Do not use `postgres` as runtime app user.
  - Treat this as a release gate even if startup guards are temporarily relaxed.
- Pooling controls:
  - These flags are resolved via standard runtime config precedence (env first, then Streamlit secrets).
  - `OKR_DB_USE_NULL_POOL` (default: `1`, recommended for Supabase PgBouncer transaction mode)
  - If `OKR_DB_USE_NULL_POOL=0`, app-side SQLAlchemy pool sizing controls apply:
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
- Environment fallback:
  - PDF_METHOD
  - OKR_PDF_METHOD
  - PDFSHIFT_API_KEY
- Behavior:
  - `pdfshift` is the only supported PDF runtime mode.
  - If PDFShift is unavailable/misconfigured, UI falls back to HTML export (no local PDF engine fallback).

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

- Strict mode default:
  - `OKR_STRICT_RUNTIME_PREFLIGHT` is enabled by default.
  - Set `OKR_STRICT_RUNTIME_PREFLIGHT=0` only for temporary troubleshooting.
- Behavior:
  - Runtime validates PDF provider mode and key presence.
  - Runtime also validates backend production-safety wiring (backend URL/token/signing secret and local-fallback policy) when relevant.
  - In strict mode, critical preflight errors stop app startup.
  - Provider configuration issues are surfaced as warnings/errors depending on severity.

Backend API (recommended for scale)

- Streamlit-to-backend routing:
  - Source precedence: environment variables first, then Streamlit secrets (root key or `[app]` section).
  - `OKR_BACKEND_API_URL` (e.g. `http://backend-api:8100`)
  - `OKR_BACKEND_SERVICE_TOKEN` (shared token for service-to-service auth)
  - `OKR_BACKEND_SIGNING_SECRET` (shared HMAC signing secret for signed internal requests)
  - `OKR_BACKEND_DEFAULT_ACTOR` (fallback actor for system-initiated AI requests; default: `system`)
  - `OKR_BACKEND_PROXY_MUTATIONS` (default: `true`; routes frontend mutation writes through backend API when backend URL is set)
  - `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` (default: `false`; emergency non-production fallback only)
- Backend API runtime:
  - `OKR_BACKEND_HOST` (default: `0.0.0.0`)
  - `OKR_BACKEND_PORT` (default: `8100`)
  - `OKR_BACKEND_ENFORCE_TOKEN` (default: `true`)
  - `OKR_BACKEND_ENFORCE_REQUEST_SIGNING` (default: `true` in production envs, otherwise `false`)
  - `OKR_BACKEND_REQUEST_SIGNING_WINDOW_SECONDS` (default: `300`)
  - `OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
  - `OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS` (default: `120`)
  - Job quota controls:
    - `OKR_BACKEND_JOB_USER_WINDOW_SECONDS` (default: `60`)
    - `OKR_BACKEND_JOB_USER_MAX_REQUESTS` (default: `8`)
    - `OKR_BACKEND_JOB_USER_DAILY_MAX_REQUESTS` (default: `200`)
    - `OKR_BACKEND_JOB_TEAM_WINDOW_SECONDS` (default: `60`)
    - `OKR_BACKEND_JOB_TEAM_MAX_REQUESTS` (default: `60`)
    - `OKR_BACKEND_JOB_TEAM_DAILY_MAX_REQUESTS` (default: `1200`)
- Backend worker runtime:
  - `OKR_BACKEND_WORKER_POLL_SECONDS` (default: `2`)
- Notes:
  - With `OKR_BACKEND_API_URL` set, frontend write flows (node CRUD, timer, users/cycles/teams, Learning Loop writes, alignments, work-log deletes) and heavy AI/PDF workflows run through backend services.
  - `OKR_BACKEND_PROXY_MUTATIONS=true` keeps mutation authority in backend API.
  - If backend transport fails, production default is fail-closed unless `OKR_ALLOW_LOCAL_BACKEND_FALLBACK=true` is explicitly set.
  - In non-production (or when strict runtime preflight is disabled), missing backend URL can result in direct-mode legacy behavior.
  - In the provided Docker Compose profile, backend API is bound to `127.0.0.1` by default for reduced exposure.
  - Current MVP still serves most read-heavy hierarchy traversal directly via Streamlit + SQLModel.

Recommended deployment profiles

- Streamlit Cloud:
  - MVP/demo only (not recommended for confidential internal company data)
  - PDF_METHOD=pdfshift
  - AI_PROVIDER=gemini (or your approved hosted gateway via `openai_compatible`)
  - pdfshift_api_key must be present
  - OKR_STRICT_RUNTIME_PREFLIGHT defaults to strict (recommended)
- Self-hosted server (Docker/VM):
  - PDF_METHOD=pdfshift
  - AI_PROVIDER=openai_compatible for local/self-hosted LLM routing
  - If openai_compatible: set AI_BASE_URL and AI_MODEL
  - Deploy `okr`, `backend-api`, and `backend-worker` services together
  - OKR_STRICT_RUNTIME_PREFLIGHT defaults to strict (recommended)
  - Recommended for confidential internal company data.

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
