Documentation HQ: [README](../README.md)

Enterprise Deployment Checklist

This checklist matches `DEPLOYMENT.md` and is optimized for:
- Docker Compose
- PostgreSQL
- Nginx
- HTTPS
- Subdomain hosting (`okr.mycompany.com`)

Mark each item complete before go-live.

Last updated: 2026-02-20

Mode selection
- If you are deploying on Streamlit Cloud, use section `A` and skip section `B`.
- If you are deploying to your own server via Docker Compose, use section `B`.

A. Streamlit Cloud checklist (MVP mode)
- [ ] App is connected to this repository in Streamlit Cloud.
- [ ] Runtime secrets are configured in Streamlit Cloud settings (not in git).
- [ ] `PDF_METHOD=pdfshift` is configured.
- [ ] `pdfshift_api_key` is configured.
- [ ] `OKR_STRICT_RUNTIME_PREFLIGHT=1` is configured (recommended for production).
- [ ] `GEMINI_API_KEY` is configured (or AI is intentionally disabled and accepted).
- [ ] App starts and login works in Streamlit Cloud.
- [ ] GitHub Actions SSH deploy step is skipped (expected when `ENABLE_SSH_DEPLOY` is unset/false).
- [ ] You understand SSH secrets are only needed later for self-hosted server deploy.
- [ ] You accept Streamlit Cloud is not the preferred mode for confidential internal company data.

B. Self-hosted checklist (Docker Compose + Nginx + TLS)

1. Prerequisites
- [ ] Server is provisioned and reachable (SSH access).
- [ ] Docker Engine and Docker Compose plugin are installed.
- [ ] Nginx is installed.
- [ ] DNS `A` record exists for `okr.mycompany.com`.
- [ ] PostgreSQL endpoint and credentials are available.
- [ ] TLS method is decided (corporate PKI or Certbot).

2. Repository And Config
- [ ] Repo is cloned on the server.
- [ ] `deploy/docker/.env` exists (copied from `deploy/docker/.env.example`).
- [ ] Optional shortcut used if applicable: `deploy/docker/.env.mycompany.example`.
- [ ] `OKR_DATABASE_URL` is set in `.env` and points to Supabase transaction pooler (`*.pooler.supabase.com:6543`).
- [ ] `OKR_DATABASE_URL` uses the least-privilege `okr_app` role (or equivalent non-superuser role), not `postgres`, for runtime operations.
- [ ] DB-role verification is completed as a release gate even if runtime startup validation is temporarily relaxed.
- [ ] `BASE_URL_PATH` is empty for subdomain deployment.
- [ ] Optional integrations secrets are prepared in `deploy/secrets/secrets.toml`.
- [ ] Deploy config validation passes: `python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml`.
- [ ] `PDF_METHOD` is explicitly set to `pdfshift`.
- [ ] If `PDF_METHOD=pdfshift`, `pdfshift_api_key` is present in secrets.
- [ ] `OKR_BACKEND_API_URL` is set (default: `http://backend-api:8100`).
- [ ] `OKR_BACKEND_SERVICE_TOKEN` is set to a strong shared secret.
- [ ] `OKR_BACKEND_SIGNING_SECRET` is set and matches across `okr` and `backend-api`.
- [ ] `OKR_BOOTSTRAP_ADMIN_PASSWORD` is set to a strong value (required in production; minimum 12 chars with upper/lowercase, number, symbol).
- [ ] `OKR_BACKEND_PROXY_MUTATIONS=true` is set (recommended for backend-owned writes).
- [ ] `OKR_BACKEND_SECURITY_STATE_BACKEND` is set to `database` or `redis` for production distributed nonce/rate-limit state.
- [ ] If `OKR_BACKEND_SECURITY_STATE_BACKEND=redis`, `OKR_BACKEND_SECURITY_STATE_REDIS_URL` is set.
- [ ] Job quota and backlog controls are set and reviewed for expected traffic:
  - `OKR_BACKEND_JOB_USER_WINDOW_SECONDS`
  - `OKR_BACKEND_JOB_USER_MAX_REQUESTS`
  - `OKR_BACKEND_JOB_USER_DAILY_MAX_REQUESTS`
  - `OKR_BACKEND_JOB_USER_PENDING_MAX_REQUESTS`
  - `OKR_BACKEND_JOB_TEAM_WINDOW_SECONDS`
  - `OKR_BACKEND_JOB_TEAM_MAX_REQUESTS`
  - `OKR_BACKEND_JOB_TEAM_DAILY_MAX_REQUESTS`
  - `OKR_BACKEND_JOB_TEAM_PENDING_MAX_REQUESTS`
  - `OKR_BACKEND_JOB_BACKOFF_BASE_SECONDS`
- [ ] `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` is unset/false in production.
- [ ] `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN` is unset/false in production (production runtime ignores fail-open overrides).
- [ ] `OKR_STRICT_RUNTIME_PREFLIGHT=1` is set (recommended for production).
- [ ] `GEMINI_API_KEY` is set (or AI-disable decision is documented).

3. App Launch
- [ ] App is started with `docker compose -f deploy/docker/docker-compose.yml up -d --build`.
- [ ] Services are running (`okr`, `backend-api`, `backend-worker` in `docker compose ... ps`).
- [ ] Local health check responds on `http://127.0.0.1:8501/`.
- [ ] Backend health check responds on `http://127.0.0.1:8100/healthz`.
- [ ] No startup migration errors in container logs.
- [ ] Async job loop is healthy (`backend-worker` consuming jobs).

4. Reverse Proxy
- [ ] Nginx config is in place (subdomain proxy to `127.0.0.1:8501`).
- [ ] Websocket headers are configured (`Upgrade`, `Connection`).
- [ ] Proxy timeouts are at least `3600` seconds.
- [ ] `nginx -t` passes.
- [ ] Nginx is reloaded successfully.

5. TLS
- [ ] HTTPS certificate is issued and installed.
- [ ] HTTP requests redirect to HTTPS.
- [ ] `curl -I https://okr.mycompany.com` returns a successful response.

6. First Login Hardening
- [ ] First login on empty production DB uses `admin/<OKR_BOOTSTRAP_ADMIN_PASSWORD>`.
- [ ] Non-production fallback `admin/admin` is not used in production environments.
- [ ] Admin password is changed immediately.
- [ ] Named admin users are created.
- [ ] Unused/test users are disabled.
- [ ] At least one OKR cycle is created.

7. Functional Smoke Tests
- [ ] Login/logout works.
- [ ] Create Goal > Objective > KR > Task works.
- [ ] Frontend mutation flows work while backend API is enabled (node CRUD, timer, user/cycle/team admin actions, Learning Loop writes, alignments).
- [ ] Timer start/stop works.
- [ ] Reports render.
- [ ] No browser reconnect loops.
- [ ] RBAC works for admin/manager/member.
- [ ] Runtime preflight shows no critical configuration errors.

8. Security And Operations
- [ ] Public access is limited to ports `80/443`.
- [ ] App port `8501` is not publicly exposed.
- [ ] Backend API port `8100` is private (bound to loopback/internal only).
- [ ] DB backups are enabled and restore tested.
- [ ] Logs are collected (Nginx + container).
- [ ] Uptime monitoring is enabled for `https://okr.mycompany.com`.
- [ ] Credential rotation process is documented.
- [ ] Secrets are only in secret manager/Streamlit secrets (never committed).

9. Upgrade And Rollback Readiness
- [ ] Upgrade commands are documented for operators.
- [ ] Previous stable image tag is recorded.
- [ ] Rollback procedure is tested at least once.

10. Optional GitHub Actions SSH Deploy
- [ ] Repository secrets are set if SSH deploy is enabled:
  - `ENABLE_SSH_DEPLOY=true`
  - `SSH_HOST` (or `DEPLOY_HOST` / `HOST`)
  - `SSH_USER` (or `DEPLOY_USER` / `USERNAME`)
  - `SSH_KEY` (or `DEPLOY_KEY`)
  - `REMOTE_DEPLOY_DIR` (or `DEPLOY_DIR`)
- [ ] `SSH_KEY` is stored in GitHub repository -> `Settings` -> `Secrets and variables` -> `Actions`.
- [ ] Private keys are never committed to the repository.

11. Git governance (recommended)
- [ ] Branch protection is enabled on main branch.
- [ ] CI must pass before merge.
- [ ] Required CI checks include:
  - Docs HQ Link Check
  - Deploy Config Template Gate
  - RBAC Regression Gate
  - Full Test job

Reference docs
- `DEPLOYMENT.md`
- `docs/CONFIG_REFERENCE.md`
- `docs/DOCKER_COMPOSE.md`
- `docs/REVERSE_PROXY.md`
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
- `docs/INTERNAL_DEPLOYMENT_CHECKLIST.md`
