Documentation HQ: [README](../README.md)

Enterprise Deployment Checklist

This checklist matches `DEPLOYMENT.md` and is optimized for:
- Docker Compose
- PostgreSQL
- Nginx
- HTTPS
- Subdomain hosting (`okr.mycompany.com`)

Mark each item complete before go-live.

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
- [ ] `OKR_DATABASE_URL` is set in `.env` and points to Supabase (`*.supabase.com`).
- [ ] `BASE_URL_PATH` is empty for subdomain deployment.
- [ ] Optional integrations secrets are prepared in `deploy/secrets/secrets.toml`.

3. App Launch
- [ ] App is started with `docker compose -f deploy/docker/docker-compose.yml up -d --build`.
- [ ] Container is running (`docker compose ... ps`).
- [ ] Local health check responds on `http://127.0.0.1:8501/`.
- [ ] No startup migration errors in container logs.

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
- [ ] Login with bootstrap account (`admin/admin`) only on first empty DB.
- [ ] Admin password is changed immediately.
- [ ] Named admin users are created.
- [ ] Unused/test users are disabled.
- [ ] At least one OKR cycle is created.

7. Functional Smoke Tests
- [ ] Login/logout works.
- [ ] Create Goal > Objective > KR > Task works.
- [ ] Timer start/stop works.
- [ ] Reports render.
- [ ] No browser reconnect loops.
- [ ] RBAC works for admin/manager/member.

8. Security And Operations
- [ ] Public access is limited to ports `80/443`.
- [ ] App port `8501` is not publicly exposed.
- [ ] DB backups are enabled and restore tested.
- [ ] Logs are collected (Nginx + container).
- [ ] Uptime monitoring is enabled for `https://okr.mycompany.com`.
- [ ] Credential rotation process is documented.

9. Upgrade And Rollback Readiness
- [ ] Upgrade commands are documented for operators.
- [ ] Previous stable image tag is recorded.
- [ ] Rollback procedure is tested at least once.

Reference docs
- `DEPLOYMENT.md`
- `docs/CONFIG_REFERENCE.md`
- `docs/DOCKER_COMPOSE.md`
- `docs/REVERSE_PROXY.md`
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
