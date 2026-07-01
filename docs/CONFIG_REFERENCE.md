Documentation HQ: [README](../README.md)

Configuration reference

Overview

- The app reads configuration from environment variables.

Database

- Environment variables:
  - OKR_DATABASE_URL (recommended)
  - DATABASE_URL (optional alias)
  - Example:
    - `postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require`
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
  - These flags are resolved via standard runtime config precedence (env first, then TOML config).
  - `OKR_DB_USE_NULL_POOL` (default: `1`, recommended for Supabase PgBouncer transaction mode)
  - If `OKR_DB_USE_NULL_POOL=0`, app-side SQLAlchemy pool sizing controls apply:
    - `OKR_DB_POOL_SIZE` (default: `5`)
    - `OKR_DB_MAX_OVERFLOW` (default: `5`)
    - `OKR_DB_POOL_TIMEOUT` (default: `30`)
    - `OKR_DB_POOL_RECYCLE` (default: `1800`)

SPA server

- Environment variables:
  - BFF_PORT (default 3001)
  - SPA Web runs on port 3000
  - CI includes quality gates in `.github/workflows/ci.yml`.

PDF generation

- Config keys:
  - PDF_METHOD: `pdfshift` or `chromium`
  - pdfshift_api_key: required only when `PDF_METHOD=pdfshift`
  - chromium_executable_path: optional executable path when `PDF_METHOD=chromium`
- Environment fallback:
  - PDF_METHOD
  - OKR_PDF_METHOD
  - PDFSHIFT_API_KEY
  - OKR_CHROMIUM_EXECUTABLE_PATH
  - CHROMIUM_EXECUTABLE_PATH
- Behavior:
  - Supported runtime modes: `pdfshift`, `chromium`
  - `pdfshift` requires API key; `chromium` requires Playwright + Chromium runtime.
  - If configured PDF renderer is unavailable/misconfigured, UI falls back to HTML export.

AI integration

- Config keys:
  - AI_PROVIDER: `gemini` (default) or `openai_compatible`
  - ALLOW_EXTERNAL_AI: policy gate (`true`/`false`); default `false`
  - GEMINI_API_KEY: required when `AI_PROVIDER=gemini`
  - GEMINI_MODEL: optional override (default: `gemini-flash-latest`)
  - AI_BASE_URL: required when `AI_PROVIDER=openai_compatible`
  - AI_MODEL: required when `AI_PROVIDER=openai_compatible`
  - AI_API_KEY: optional token for OpenAI-compatible gateways
  - AI_REQUEST_TIMEOUT_SECONDS: optional provider read timeout for OpenAI-compatible calls (default: `120`)
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
  - AI_REQUEST_TIMEOUT_SECONDS
  - OPENAI_REQUEST_TIMEOUT_SECONDS
  - ALLOW_EXTERNAL_AI
  - OKR_ALLOW_EXTERNAL_AI
- Behavior:
  - If `ALLOW_EXTERNAL_AI=false`, outbound AI calls are blocked regardless of provider.
  - `AI_PROVIDER=openai_compatible` uses Chat Completions-style APIs, so self-hosted models can be used without Gemini.
  - Runtime preflight reports this policy as an informational status.

SPA AI sync controls

- `NEXT_PUBLIC_OKR_AI_SYNC_MAX_DELTA` (default: `100`): maximum KR point change allowed per AI sync run.
- `NEXT_PUBLIC_OKR_AI_SYNC_ALLOW_DECREASE` (default: `true`): allow AI to lower KR progress values. Set to `false` to only allow increases.

Runtime preflight policy

- Strict mode default:
  - `OKR_STRICT_RUNTIME_PREFLIGHT` is enabled by default.
  - Set `OKR_STRICT_RUNTIME_PREFLIGHT=0` only for temporary troubleshooting.
- Behavior:
  - Runtime validates PDF provider mode and key presence.
  - Runtime also validates backend production-safety wiring (backend URL/token/signing secret/distributed security backend).
  - Production requires `OKR_BOOTSTRAP_ADMIN_PASSWORD` and it must be strong (minimum 12 chars including upper/lowercase, number, symbol).
  - Production backend mode requires `OKR_BACKEND_SECURITY_STATE_BACKEND=database` or `redis` for distributed nonce/rate-limit state.
  - If `OKR_BACKEND_SECURITY_STATE_BACKEND=redis`, set `OKR_BACKEND_SECURITY_STATE_REDIS_URL`.
  - In strict mode, critical preflight errors stop app startup.
  - Provider configuration issues are surfaced as warnings/errors depending on severity.

Backend API (recommended for scale)

- Deployment intent:
  - Corporate/self-hosted production should run a separate backend server tier (`backend-api` + `backend-worker`).
- Frontend-to-backend routing:
  - Source precedence: environment variables first, then TOML config files.
  - `OKR_BACKEND_API_URL`:
    - Example: `http://backend-api:8100`
  - `OKR_BACKEND_SERVICE_TOKEN`: Shared token for service-to-service auth.
  - `OKR_BACKEND_SIGNING_SECRET`: Shared HMAC signing secret for signed internal requests.
  - `OKR_BACKEND_DEFAULT_ACTOR`: Fallback actor for system-initiated AI requests; default: `system`.
  - `OKR_BACKEND_PROXY_MUTATIONS` (required secure value: `true`): frontend write operations are backend-owned in runtime.
  - `OKR_BACKEND_PROXY_READS` (required secure value: `true`): frontend read operations are backend-owned in runtime.
  - `OKR_ALLOW_LOCAL_MUTATION_FALLBACK` (required secure value: `false`): retained as deployment-policy gate; runtime executes fail-closed.
  - `OKR_ALLOW_LOCAL_READ_FALLBACK` (required secure value: `false`): retained as deployment-policy gate; runtime executes fail-closed.
  - `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` (legacy key): keep `false`; runtime local fallback is not used.
  - `OKR_ENABLE_DIRECT_DB_RESTORE` (default: `false`): Direct DB restore is disabled by default and blocked in production.
- Backend API runtime:
  - `OKR_BACKEND_HOST` (default: `0.0.0.0`)
  - `OKR_BACKEND_PORT` (default: `8100`)
  - `OKR_BACKEND_ENFORCE_TOKEN` (default: `true`)
  - `OKR_BACKEND_ENFORCE_REQUEST_SIGNING` (default: `true` in production envs, otherwise `false`)
  - `OKR_BACKEND_SECURITY_STATE_BACKEND` (`database` in production by default, `memory` in non-production by default; supported values: `memory`, `database`, `redis`)
  - `OKR_BACKEND_SECURITY_STATE_REDIS_URL` (required when backend is `redis`)
  - `OKR_BACKEND_SECURITY_STATE_REDIS_PREFIX` (optional Redis key namespace; default: `okr:security`)
  - `OKR_BACKEND_SECURITY_STATE_CLEANUP_SECONDS` (default: `60`)
  - `OKR_BACKEND_REQUEST_SIGNING_WINDOW_SECONDS` (default: `300`)
  - `OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
  - `OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS` (default: `120`)
  - Job quota controls:
    - `OKR_BACKEND_JOB_USER_WINDOW_SECONDS` (default: `60`)
    - `OKR_BACKEND_JOB_USER_MAX_REQUESTS` (default: `8`)
    - `OKR_BACKEND_JOB_USER_DAILY_MAX_REQUESTS` (default: `200`)
    - `OKR_BACKEND_JOB_USER_PENDING_MAX_REQUESTS` (default: `3`; max active `pending`/`running` jobs per user)
    - `OKR_BACKEND_JOB_TEAM_WINDOW_SECONDS` (default: `60`)
    - `OKR_BACKEND_JOB_TEAM_MAX_REQUESTS` (default: `60`)
    - `OKR_BACKEND_JOB_TEAM_DAILY_MAX_REQUESTS` (default: `1200`)
    - `OKR_BACKEND_JOB_TEAM_PENDING_MAX_REQUESTS` (default: `40`; max active `pending`/`running` jobs per team)
    - `OKR_BACKEND_JOB_BACKOFF_BASE_SECONDS` (default: `3`; minimum spacing between new submissions per actor; set `0` to disable)
  - Backend worker runtime:
  - `OKR_BACKEND_WORKER_POLL_SECONDS` (default: `2`)
  - `OKR_BACKEND_JOB_RETENTION_DAYS` (default: `14`; terminal async job retention before prune)
  - `OKR_BACKEND_AUDIT_RETENTION_DAYS` (default: `365`; `audit_event` retention before prune)
  - `OKR_BACKEND_JOB_PRUNE_INTERVAL_SECONDS` (default: `300`; worker prune cadence)
  - `OKR_BACKEND_JOB_PRUNE_BATCH_SIZE` (default: `200`; max rows removed per prune pass)
  - Built-in resiliency guards (non-configurable):
    - Job `max_attempts` is normalized and hard-capped in persistence.
    - Malformed/non-retryable payload failures are marked terminal (no infinite requeue).
    - Worker loop catches generic iteration errors to avoid queue poison-pill stalls.
- Notes:
  - With `OKR_BACKEND_API_URL` set, frontend read/write flows (node CRUD, timer, users/cycles/teams, Learning Loop writes, alignments, work-log deletes, Atlas/leadership reads) and heavy AI/PDF workflows run through backend services.
  - `OKR_BACKEND_PROXY_MUTATIONS=true` and `OKR_BACKEND_PROXY_READS=true` keep application authority in backend API contracts.
  - Job submit endpoint (`POST /v1/jobs`) supports idempotency via `X-OKR-Idempotency-Key`.
  - Quota/backoff rejections return deterministic `429` payloads with `detail.error_code`, `detail.retry_after_seconds`, and `Retry-After` header.
  - Job submit accepted/rejected events are written to DB-backed `audit_event` (with file fallback) for usage reporting and incident review.
  - `OKR_BACKEND_SECURITY_STATE_BACKEND=database` stores request-signing nonces and backend API rate-limit counters in shared DB tables (`backend_request_nonce`, `backend_rate_limit_counter`) so controls are consistent across replicas.
  - `OKR_BACKEND_SECURITY_STATE_BACKEND=redis` stores nonce/rate-limit counters in shared Redis keys; set `OKR_BACKEND_SECURITY_STATE_REDIS_URL` and optionally `OKR_BACKEND_SECURITY_STATE_REDIS_PREFIX`.
  - If proxied backend transport fails, runtime behavior is fail-closed (local read/mutation fallback execution is disabled).
  - Direct DB restore is opt-in (`OKR_ENABLE_DIRECT_DB_RESTORE=true`) and intended for controlled non-production scenarios only.
  - In the provided Docker Compose profile, backend API is bound to `127.0.0.1` by default for reduced exposure.

Recommended deployment profiles

- Docker Compose (local dev):
  - PDF_METHOD=pdfshift (recommended)
  - AI_PROVIDER=gemini (or your approved hosted gateway via `openai_compatible`)
  - pdfshift_api_key must be present
  - OKR_STRICT_RUNTIME_PREFLIGHT defaults to strict (recommended)
- Self-hosted server (Docker/VM):
  - PDF_METHOD=pdfshift or PDF_METHOD=chromium
  - If `PDF_METHOD=pdfshift`: `pdfshift_api_key` must be present
  - If `PDF_METHOD=chromium`: install Playwright and Chromium runtime
  - AI_PROVIDER=openai_compatible for local/self-hosted LLM routing
  - If openai_compatible: set AI_BASE_URL and AI_MODEL
  - Deploy `spa-web`, `spa-bff`, `backend-api`, and `backend-worker` services together
  - OKR_STRICT_RUNTIME_PREFLIGHT defaults to strict (recommended)
  - Recommended for confidential internal company data.

Release governance (CI)

- Branches should require passing CI checks before merge:
  - Docs HQ link check
  - Deploy config template gate
  - Quality baseline expiry gate (`scripts/check_quality_gate_baseline.py`)
  - Repo-critical lint gate (Ruff `E9,F63,F7,F82` across `backend_app`, `scripts`, `tests`)
  - Expanded mypy gate (`scripts`, `backend_app` runtime-core modules)
  - RBAC regression gate
  - Session-state governance gate
  - Full pytest suite
  - Playwright happy-path e2e (`Login -> Focus Map -> Start Timer`)
- Time-boxed baseline policy:
  - Temporary quality-scope exceptions are tracked in `docs/QUALITY_GATE_BASELINE.md`.
  - Expiry enforcement runs in CI/pre-commit via `scripts/check_quality_gate_baseline.py`.
- OKR governance policy artifacts:
  - Strategic-change vs BAU boundary policy: `docs/OKR_BAU_BOUNDARY_GUIDE.md`.
  - BAU release decision log template: `docs/templates/OKR_BAU_RELEASE_LOG_TEMPLATE.md`.
- Before production release, run runtime config gate workflow:
  - GitHub Actions workflow: `.github/workflows/release-runtime-gate.yml` (`workflow_dispatch`)
  - Required repository/environment secrets:
    - `OKR_RUNTIME_ENV_DOTENV` (runtime `.env` content)
  - Gate command executed by workflow:
    - `python scripts/check_deploy_config.py --mode runtime --env-file /tmp/okr-runtime-gate/runtime.env`

Admin bootstrap

- On first run (empty DB), an admin user is created:
  - username: `admin`
  - password:
    - production: `OKR_BOOTSTRAP_ADMIN_PASSWORD` (required; minimum 12 chars including upper/lowercase, number, symbol)
    - non-production: defaults to `admin` for local/dev convenience
- The initial admin is forced to change password on first login.
- `OKR_BOOTSTRAP_ADMIN_PASSWORD` is read from environment variables at runtime.

Authentication policy controls

- `OKR_ENFORCE_STRONG_PASSWORD_POLICY`
  - default: enabled in production, disabled in non-production
  - when enabled, create/reset password requests must be at least 12 characters and include uppercase, lowercase, number, and symbol
  - this policy is enforced in both backend API request validation and CRUD mutation paths
- `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN`
  - default: disabled in production, enabled in non-production
  - in production, fail-open is forcibly disabled even if the variable is set
  - auth-throttle operational failures return temporary auth unavailability (`AUTH_TEMP_UNAVAILABLE`) instead of bypassing throttle checks

Logging & health

- HTTP health check: GET /healthz
- Logs: backend-api stdout/stderr (container logs or service logs)
- Audit trail:
  - Primary: `audit_event` table (`actor`, `action`, `entity`, `result`, `details_json`, `created_at`, correlation/request ids).
  - Worker-driven retention: `OKR_BACKEND_AUDIT_RETENTION_DAYS` (default `365`).
