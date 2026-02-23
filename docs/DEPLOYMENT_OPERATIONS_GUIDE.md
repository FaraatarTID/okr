Documentation HQ: [README](../README.md)

# Deployment Operations Guide (Consolidated)

This is the canonical English guide for deployment execution, go-live checks, internal rollout gates, and day-2 operations.

It consolidates the previously duplicated runbook/checklist/operations content into one maintained reference.

Last updated: 2026-02-22

## 1. Use This Guide For
- First production deployment on Docker Compose or Kubernetes.
- Pre-go-live security and configuration sign-off.
- Internal pilot rollout checks.
- Routine operations and incident response.

## 2. Required Baseline (Production)
- `OKR_BACKEND_PROXY_MUTATIONS=true`
- `OKR_BACKEND_API_URL` set and reachable
- `OKR_BACKEND_SERVICE_TOKEN` set (strong secret)
- `OKR_BACKEND_SIGNING_SECRET` set
- `OKR_BACKEND_SECURITY_STATE_BACKEND=database|redis`
- If `redis`: `OKR_BACKEND_SECURITY_STATE_REDIS_URL` set
- `OKR_BOOTSTRAP_ADMIN_PASSWORD` set (strong)
- `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=false`
- `OKR_ALLOW_LOCAL_READ_FALLBACK=false`
- `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false`
- `OKR_STRICT_RUNTIME_PREFLIGHT=true`
- PDF renderer configured:
  - `PDF_METHOD=pdfshift` + `pdfshift_api_key`, or
  - `PDF_METHOD=chromium` + Playwright/Chromium runtime

Validate before startup:
```bash
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env --secrets-file deploy/secrets/secrets.toml
```

## 3. First Deployment Workflow
1. Provision infra (server/cluster, DB, reverse proxy, TLS, DNS).
2. Prepare runtime config (`deploy/docker/.env`, `deploy/secrets/secrets.toml`).
3. Run deploy-config validation command above.
4. Launch stack:
   - Compose: `docker compose -f deploy/docker/docker-compose.yml up -d --build`
   - Kubernetes: apply manifests under `deploy/k8s/`
5. Verify health:
   - App: `GET /`
   - Backend API: `GET /healthz`
6. First login hardening:
   - production: `admin/<OKR_BOOTSTRAP_ADMIN_PASSWORD>`
   - change password immediately
   - create named admins and disable test users

## 4. Go-Live Checklist (Condensed)
- Runtime preflight shows no critical errors.
- Backend-owned writes work end-to-end (CRUD/timer/admin/learning-loop/alignment).
- Async jobs work end-to-end (`backend-worker` consumes AI/PDF jobs).
- RBAC works for admin/manager/member.
- Ports are hardened (public: `80/443` only; backend private).
- Backup + restore has been tested.
- Monitoring and log collection are active.

## 5. Internal Pilot Security Gates
- Review and execute: `docs/V2_PRIORITIZED_ISSUE_LIST.md`
- Confirm least-privilege DB role in runtime DSN (never `postgres`).
- Keep backend API private/internal only.
- Keep scoped fallback flags disabled in production.
- Confirm AI provider/data-flow policy approval before enabling external AI.

Recommended targeted guard tests during rollout:
```bash
python -m pytest tests/test_streamlit_form_guardrails.py -q
python -m pytest tests/test_auth_rate_limit.py -q
python -m pytest tests/test_selector_integrity_guardrails.py -q
python -m pytest tests/test_atlas_cache_performance.py -q
python -m pytest tests/test_database_engine_pooling.py -q
```

## 6. Day-2 Operations
- Monitor uptime (`/`, `/healthz`) and reverse-proxy/container logs.
- Track backend `/v1/jobs` quota pressure (`429`, `Retry-After`).
- Review audit events: `job_submit_accepted`, `job_submit_rejected`.
- Rotate secrets on schedule.
- Keep dependencies current and preserve CI required checks on main.

## 7. Incident Response
- Treat strict preflight startup blocks as config incidents.
- Snapshot before risky changes.
- Use tested rollback procedure (image tag + config rollback).
- For non-production emergency only, enable scoped fallback temporarily:
  - `OKR_ALLOW_LOCAL_MUTATION_FALLBACK=true` for mutation/timer/job paths
  - `OKR_ALLOW_LOCAL_READ_FALLBACK=true` for proxied reads
- Disable emergency fallback immediately after incident stabilization.

## 8. Related References
- Full deployment walkthrough: `DEPLOYMENT.md`
- Configuration key details: `docs/CONFIG_REFERENCE.md`
- Compose specifics: `docs/DOCKER_COMPOSE.md`
- Kubernetes specifics: `docs/KUBERNETES.md`
- Reverse proxy specifics: `docs/REVERSE_PROXY.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
