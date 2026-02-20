Documentation HQ: [README](../README.md)

Docker Compose deployment

Stack services
- `okr` (Streamlit UI)
- `backend-api` (internal FastAPI service for node mutations, timer, and jobs)
- `backend-worker` (async worker for AI/PDF jobs)

Service interaction
- `okr` sends authenticated backend calls using `OKR_BACKEND_SERVICE_TOKEN`.
- With `OKR_BACKEND_PROXY_MUTATIONS=true` (default), Goal/Objective/KR/Task writes route via `backend-api`.
- `backend-api` persists async jobs in primary DB (`async_job` table).
- `backend-worker` executes queued job kinds (`ai.generate_json`, `pdf.weekly`).
- If backend is unavailable, supported paths degrade to local fallback behavior.

Single host, subdomain (recommended)
- Copy `deploy/docker/.env.example` to `deploy/docker/.env`
- Keep `BASE_URL_PATH` empty for subdomain mode
- Set required values:
  - `OKR_DATABASE_URL` (Supabase transaction pooler `:6543` + `sslmode=require`)
  - `OKR_BACKEND_SERVICE_TOKEN` (shared token for UI -> backend-api auth)
  - `OKR_BACKEND_PROXY_MUTATIONS=true` (recommended)
  - `PDFSHIFT_API_KEY` (required for PDF binary exports)
- Build and start:
  - `docker compose -f deploy/docker/docker-compose.yml up -d --build`
- Place Nginx in front using `deploy/nginx.conf` (TLS termination at proxy)

Single host, subpath
- Set `BASE_URL_PATH` to desired prefix (for example `okr`)
- Use the subpath location in deploy/nginx.conf (with rewrite removing the prefix)

Starting with PostgreSQL
- Required: Supabase PostgreSQL
  - Set `OKR_DATABASE_URL` in environment (`.env`)
  - Use the transaction pooler URL (`:6543`) with `sslmode=require`

Secrets
- Create a secrets file if using integrations and mount as:
  - /app/streamlit_app/.streamlit/secrets.toml
- Use deploy/secrets/secrets.toml.example as a template
- If you do not mount secrets, set equivalent env vars in `.env` (PDF/AI settings).

Persistence
- All runtime data is stored in Supabase PostgreSQL
- Ensure DB backups are enabled

Health & logs
- App health: `GET /` should return `200`
- Backend health (host-local by default): `GET http://127.0.0.1:${OKR_BACKEND_HOST_PORT:-8100}/healthz`
- Logs:
  - `docker compose logs okr`
  - `docker compose logs backend-api`
  - `docker compose logs backend-worker`

Upgrades
- Pull code/image; rebuild and restart compose services

Rollback
- Recreate container with previous image tag
