Documentation HQ: [README](README.md)

Lifecycle: Operational | Owner: Platform/Operations | Last reviewed: 2026-08-31

Enterprise Deployment Guide (Step-by-Step, Beginner Friendly)

Last updated: 2026-02-20

This guide is for deploying the OKR app in a company environment where users access it through a corporate URL such as:

- `https://okr.mycompany.com` (recommended)
- `https://mycompany.com/okr` (supported)

If you are not sure what to choose, use this default stack:

- Docker Compose
- Supabase PostgreSQL
- Nginx reverse proxy
- HTTPS (TLS certificate)

This is the safest and easiest enterprise path for this repo.

### SaaS versus compatibility data access

Cloud SaaS multi-tenancy requires direct PostgreSQL access through the approved
transaction-mode pooler (`:6543`). Tenant context is set with `SET LOCAL` in
the same transaction as the queries, allowing PostgreSQL RLS to remain the
authoritative database backstop.

The Supabase HTTPS data-access mode exists for alpha testing and selected
self-hosted environments where direct database connectivity is unavailable.
It is not a SaaS fallback. Do not enable it for a multi-tenant SaaS deployment;
the API adapter cannot provide the same session-local RLS context. If this
boundary is ever changed, require a new threat model, filtering-parity tests,
and an approved architecture decision first.

---

Architecture status and deployment intent (2026-02-24)

- The app is designed for backend-server operation in enterprise environments (`spa-web` + `spa-bff` + `backend-api` + `backend-worker`).
- For corporate deployments (AWS/ECS/Kubernetes/VM), use the backend-server model from this guide.
- The distributed resilience plan items are implemented:
  - cluster-wide cache invalidation signaling
  - URL-backed navigation-pointer restoration/synchronization
  - resilience verification scripts (`scripts/verify_resilience.py`)

Readiness conclusion for corporate backend-server deployment:

- Purpose fulfilled for operational backend-server deployment guidance and resilience controls.
- Remaining optional improvement for "easier AWS onboarding": add first-party AWS IaC blueprints (for example ECS/Fargate and RDS templates) beyond the current platform-agnostic Docker/Kubernetes guidance.

---

What this deployment gives you

- Non-root container runtime
- Automatic DB migrations at app startup
- Health checks and restart policy
- Reverse-proxy compatible with websocket traffic
- Internal backend API + async worker for timer/PDF/AI heavy flows
- Optional CI/CD via GitHub Actions

Key files used by this guide

- `deploy/docker/Dockerfile`
- `deploy/docker/docker-compose.yml`
- `deploy/docker/.env.example`
- `deploy/docker/.env.mycompany.example`
- `deploy/nginx.conf`
- `deploy/nginx.okr.mycompany.com.conf`
- `.github/workflows/docker-deploy.yml`

Workspace dependency contract

- The repository Docker runtime installs Python dependencies from the committed
  `pyproject.toml` and `uv.lock` with `uv sync --frozen --no-dev`.
- CI validates the same locked graph with `uv sync --locked`; deployment workflows
  should not replace this with an unconstrained install.
- External non-Docker environments may continue using
  `backend_app/requirements.txt` as a compatibility fallback, but must verify
  equivalence against the root manifest and lockfile first.
- Deployment review acceptance is: `uv lock --check` passes, the Docker image
  builds successfully, and the target environment records its installer and
  lockfile revision.

---

Quick decision matrix

1. Which URL structure?

- Use subdomain if possible: `okr.mycompany.com`
- Use subpath only if your company policy requires it: `mycompany.com/okr`

2. Which database?

- Required: Supabase PostgreSQL (Transaction Pooler URL on port `6543` with `sslmode=require`)

3. Which platform?

- Start with Docker Compose on one VM
- Use Kubernetes only if your team already runs K8s operationally

---

Deployment modes (important)

Use one of these modes:

1. Docker Compose on your own server (enterprise/self-hosted)

- SSH deploy is disabled by default. Set `ENABLE_SSH_DEPLOY=true` (repo secret or variable) before adding SSH deploy secrets.
- Use this when you want GitHub Actions to connect to your server and run `docker compose`.

Architecture profile (recommended)

- Use backend-assisted profile:
  - `spa-web` + `spa-bff` + `backend-api` + `backend-worker`
  - shared DB + internal service token
- This isolates heavy AI/PDF work and improves operational resilience.
- Keep backend API internal; do not expose it via public reverse proxy.

---

Path A (recommended): Docker Compose + Postgres + Nginx + TLS

Use this if you want the fastest reliable enterprise deployment.

Step 0: Collect required values

Prepare these values first:

- `APP_DOMAIN`: for example `okr.mycompany.com`
- `SERVER_IP`: public/private server IP
- `OKR_DATABASE_URL`: example `postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require`
- `CONTACT_EMAIL`: certificate contact email

Step 1: Prepare the Linux host (Ubuntu example)

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release nginx

# Install Docker Engine + Compose plugin (official repo method)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker "$USER"
newgrp docker
```

Step 2: Pull the project

```bash
git clone <YOUR_REPO_URL> okr
cd okr
```

Step 3: Configure app environment

```bash
cp deploy/docker/.env.example deploy/docker/.env
```

If you are deploying exactly to `okr.mycompany.com`, you can start from the prefilled template:

```bash
cp deploy/docker/.env.mycompany.example deploy/docker/.env
```

Edit `deploy/docker/.env` and set at minimum:

```dotenv
# Required
SPA_WEB_HOST_PORT=3000
SPA_WEB_BIND_ADDRESS=127.0.0.1
BFF_PUBLIC_ORIGIN=http://spa-bff:3001
OKR_DATABASE_URL=postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require
OKR_BACKEND_API_URL=http://backend-api:8100
OKR_BACKEND_SERVICE_TOKEN=CHANGE_ME_STRONG_SHARED_TOKEN
OKR_BACKEND_SIGNING_SECRET=CHANGE_ME_STRONG_SIGNING_KEY
OKR_BOOTSTRAP_ADMIN_PASSWORD=CHANGE_ME_STRONG_BOOTSTRAP_PASSWORD
OKR_BACKEND_ENFORCE_REQUEST_SIGNING=true
OKR_BACKEND_PROXY_MUTATIONS=true
OKR_BACKEND_SECURITY_STATE_BACKEND=database
OKR_BACKEND_SECURITY_STATE_REDIS_URL=
OKR_BACKEND_SECURITY_STATE_REDIS_PREFIX=okr:security
OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false
OKR_ENFORCE_STRONG_PASSWORD_POLICY=true
PDF_METHOD=pdfshift
PDFSHIFT_API_KEY=CHANGE_ME_PDFSHIFT_KEY
# Optional for Chromium mode:
# PDF_METHOD=chromium
# OKR_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ALLOW_EXTERNAL_AI=false
NEXT_PUBLIC_OKR_AI_SYNC_MAX_DELTA=100
NEXT_PUBLIC_OKR_AI_SYNC_ALLOW_DECREASE=true
OKR_STRICT_RUNTIME_PREFLIGHT=true

# Optional image pin (recommended after first stable release)
# IMAGE=ghcr.io/your-org/okr-backend-api:2026-02-14
```

Notes:

- Keep `BASE_URL_PATH` empty for subdomain hosting.
- For subpath hosting (`/okr`), set `BASE_URL_PATH=okr`.
- `OKR_DATABASE_URL` must use the least-privilege `okr_app` role (or equivalent non-superuser role), never `postgres`, for runtime app traffic.
- Enforce the DB-role check in deployment review/checklists even during periods where startup guards are temporarily relaxed.
- Keep `OKR_BACKEND_PROXY_MUTATIONS=true` so Goal/Objective/KR/Task writes route via backend API.
- Keep `OKR_BACKEND_SECURITY_STATE_BACKEND` on a distributed backend (`database` or `redis`) in production so nonce replay and backend rate-limit state are shared across replicas.
- If `OKR_BACKEND_SECURITY_STATE_BACKEND=redis`, set `OKR_BACKEND_SECURITY_STATE_REDIS_URL` (and optionally `OKR_BACKEND_SECURITY_STATE_REDIS_PREFIX`).
- Keep `OKR_ALLOW_LOCAL_BACKEND_FALLBACK` unset/false in production (fail-closed behavior).
- In production, set `OKR_BOOTSTRAP_ADMIN_PASSWORD` before first startup (minimum 12 chars including uppercase, lowercase, number, symbol).
- Keep `OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN` unset/false in production; production runtime ignores fail-open overrides and returns `AUTH_TEMP_UNAVAILABLE` on throttle subsystem errors.

Step 4: Validate deploy config policy

```bash
python scripts/check_deploy_config.py --mode runtime --env-file deploy/docker/.env
```

Expected:

- Exit code `0`
- No `ERROR:` lines in output

Step 6: Start the application

From repo root:

```bash
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

Health check:

```bash
docker compose -f deploy/docker/docker-compose.yml ps
curl -I http://127.0.0.1:3000/
curl -f http://127.0.0.1:8100/healthz
```

Expected:

- Services `spa-web`, `spa-bff`, `backend-api`, and `backend-worker` are `Up`
- HTTP response from `/` is `200 OK`
- Backend health endpoint returns `{"status":"ok"}`

Step 7: Configure Nginx reverse proxy

Fastest path for this exact domain:

```bash
sudo cp deploy/nginx.okr.mycompany.com.conf /etc/nginx/sites-available/okr.conf
```

Create a site file:

```bash
sudo tee /etc/nginx/sites-available/okr.conf > /dev/null <<'EOF'
server {
    listen 80;
    server_name okr.mycompany.com;

    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
EOF
```

Enable and validate Nginx:

```bash
sudo ln -sf /etc/nginx/sites-available/okr.conf /etc/nginx/sites-enabled/okr.conf
sudo nginx -t
sudo systemctl reload nginx
```

Step 8: Create DNS record

In your DNS provider:

- Add `A` record: `okr.mycompany.com -> SERVER_IP`

Wait for propagation and confirm:

```bash
nslookup okr.mycompany.com
```

Step 9: Enable HTTPS (TLS)

Using Certbot (public CA):

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d okr.mycompany.com -m your-email@company.com --agree-tos --redirect --non-interactive
```

If your company uses internal PKI, install certificates per your security policy instead of Certbot.

Step 10: First login and hardening

On first run with empty DB:

- Production: login is `admin / <OKR_BOOTSTRAP_ADMIN_PASSWORD>`
- Non-production/dev: fallback `admin / admin` remains for local convenience
- You will be forced to change password

Immediately after login:

1. Change admin password to a strong one.
2. Create named admin accounts for real admins.
3. Disable unused accounts.
4. Create initial OKR cycle.
5. Verify role-based access for manager/member users.

Step 11: Validate production readiness

Run these checks:

```bash
# App reachable over HTTPS
curl -I https://okr.mycompany.com

# Container logs
docker compose -f deploy/docker/docker-compose.yml logs --tail=200 spa-web
docker compose -f deploy/docker/docker-compose.yml logs --tail=200 spa-bff
docker compose -f deploy/docker/docker-compose.yml logs --tail=200 backend-api
docker compose -f deploy/docker/docker-compose.yml logs --tail=200 backend-worker

# Confirm proxy configuration active
sudo nginx -t
```

Confirm manually:

- Login works
- Create Goal/Objectives/KRs/Tasks
- Timer starts/stops
- Reports load
- PDF export works (via configured renderer: PDFShift or Chromium)
- No websocket reconnect loops in browser

---

Path B: Horizontal Cluster Scaling (Kubernetes / ECS / Nomad)

Use this if you need high availability or need to scale compute resources independently. In this mode, services are **de-coupled** into separate containers.

### 1. De-coupled Architecture

A cluster deployment splits the app into three distinct tiers:

```mermaid
graph TD
    User((User)) --> LB[Load Balancer / Ingress]
    LB -- "HTTP/WS" --> SPA[SPA Frontend Replicas]
    LB -- "Internal" --> API[Backend API Replicas]
    API --> DB[(Shared PostgreSQL)]
    SPA -- "Authenticated API Calls" --> API
    Worker[Backend Worker Replicas] --> DB
    Worker --> API

    subgraph "Shared State"
        DB
        Redis[(Redis Cache)]
    end
    API -.-> Redis
    ST -.-> Redis
```

### 2. Service Separation

| Service              | Replicas | Scaling Trigger | Notes                                            |
| :------------------- | :------- | :-------------- | :----------------------------------------------- |
| **`spa-web`**        | 2+       | User Sessions   | Must use **Sticky Sessions** (Session Affinity). |
| **`spa-bff`**        | 2+       | User Sessions   | Browser-facing API boundary.                     |
| **`backend-api`**    | 2+       | Request Latency | Handles all DB writes and token verification.    |
| **`backend-worker`** | 1+       | Queue Depth     | Handles async tasks (AI, PDF generation).        |

### 3. Critical Cluster Configuration

To run successfully in a cluster, set these environment variables:

- **`OKR_BACKEND_API_URL`**: Set this to the internal cluster DNS name of the backend service (e.g., `http://okr-backend-api.svc.cluster.local:8100`).
- **`OKR_BACKEND_SECURITY_STATE_BACKEND`**: Set to `database` or `redis`. Do **NOT** use `memory` in a cluster, or nonces will fail across replicas.
- **`OKR_BACKEND_SECURITY_STATE_REDIS_URL`**: Required if using Redis for high-speed rate limiting and state shared across pods.
- **`OKR_ALLOW_LOCAL_BACKEND_FALLBACK`**: Always `false` in clusters to ensure architectural integrity.

### 4. Kubernetes Implementation

Manifests are provided in `deploy/k8s/`.

1. **Namespace**: `kubectl create ns okr`
2. **Secrets**: Create a `Secret` for `OKR_DATABASE_URL` and `OKR_BACKEND_SERVICE_TOKEN`.
3. **Stickiness**: Ensure your Ingress controller is configured for stickiness:
   ```yaml
   # nginx-ingress example
   nginx.ingress.kubernetes.io/affinity: "cookie"
   nginx.ingress.kubernetes.io/session-cookie-name: "route"
   ```

Detailed configuration reference:

- `docs/CONFIG_REFERENCE.md`
- `docs/KUBERNETES.md` (Legacy reference)

---

Operations (day 2)

Logs

```bash
docker compose -f deploy/docker/docker-compose.yml logs -f spa-web
docker compose -f deploy/docker/docker-compose.yml logs -f spa-bff
docker compose -f deploy/docker/docker-compose.yml logs -f backend-api
docker compose -f deploy/docker/docker-compose.yml logs -f backend-worker
```

Restart app

```bash
docker compose -f deploy/docker/docker-compose.yml restart spa-web spa-bff backend-api backend-worker
```

Upgrade (same server, new code/image)

```bash
git pull
docker compose -f deploy/docker/docker-compose.yml pull || true
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

Rollback (if new release is bad)

1. Pin previous image tag in `deploy/docker/.env` using `IMAGE=...`.
2. Recreate containers:

```bash
docker compose -f deploy/docker/docker-compose.yml up -d
```

Backups

- Supabase PostgreSQL: enable provider snapshots and test restore quarterly.

---

Security hardening checklist

- Use Supabase PostgreSQL only.
- Keep only ports 80/443 exposed publicly.
- Block direct public access to port 3000 (SPA) and 3001 (BFF).
- Keep backend API port (`8100`) private (default bind: `127.0.0.1`).
- Use signed internal requests (`OKR_BACKEND_SIGNING_SECRET`) and keep enforcement enabled.
- Keep secrets in environment variables or platform secret manager.
- Do not commit secrets to git.
- Rotate DB/API credentials periodically.
- Keep TLS certificates valid and auto-renewed.
- Monitor auth lockout behavior and audit/error logs.

---

Common mistakes and fixes

Blank page or repeated reconnect:

- Check Nginx websocket headers (`Upgrade`, `Connection`) and 3600s timeouts.

Assets broken under subpath:

- Set `BASE_URL_PATH=okr`.
- Ensure reverse proxy strips `/okr` before forwarding.

App fails at startup with database URL error:

- Ensure `OKR_DATABASE_URL` uses `postgresql+psycopg2://` and points to `*.pooler.supabase.com:6543`.
- Ensure DSN user is `okr_app` (or equivalent least-privilege role), not `postgres`.

Cannot log in:

- If DB is new in production, confirm `OKR_BOOTSTRAP_ADMIN_PASSWORD` is set and use that value.
- If DB is new in non-production, `admin/admin` is available by default.
- If DB is existing, default admin bootstrap does not run again.

---

CI/CD option (GitHub Actions)

Workflow file:

- `.github/workflows/docker-deploy.yml`

What it can do:

- Build and push image to GHCR on push to `main`/`master`
- Optional remote deploy over SSH (self-hosted mode only, opt-in via `ENABLE_SSH_DEPLOY=true`)

Recommended for internal networks:

- Prefer pull-based deployment (server-side pull/agent/cron) to avoid granting CI direct SSH into internal hosts.
- Keep SSH push deployment only for explicitly approved environments.

Required secrets for SSH deploy (recommended names):

- `ENABLE_SSH_DEPLOY` = `true`
- `SSH_HOST`
- `SSH_USER`
- `SSH_KEY`
- `REMOTE_DEPLOY_DIR`

Supported fallback secret names in this repo's workflow:

- Host: `SSH_HOST` or `DEPLOY_HOST` or `HOST`
- User: `SSH_USER` or `DEPLOY_USER` or `USERNAME`
- Key: `SSH_KEY` or `DEPLOY_KEY`
- Deploy dir: `REMOTE_DEPLOY_DIR` or `DEPLOY_DIR`

Where to set `SSH_KEY`:

- GitHub repository -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`
- Name it `SSH_KEY` (or `DEPLOY_KEY` if you prefer fallback naming)
- Paste the private key content for your deploy user (for example, `id_ed25519` private key)

Tip:

- Use immutable image tags for controlled rollback.

Security note:

- Never commit private keys or any deploy secrets to the repository.

---

## Signing Key Rotation Runbook

Request signing between `spa-bff` and `backend-api` uses HMAC-SHA256 over a
canonical payload. Rotation is config-only — no code deploy required.

### Configuration keys

| Key | Meaning |
|---|---|
| `OKR_BACKEND_SIGNING_SECRET` | Current (signing) secret |
| `OKR_BACKEND_SIGNING_SECRET_PREVIOUS` | Previous secret, still accepted during overlap |
| `OKR_BACKEND_SIGNING_KEY_ID` | Advertised key ID (e.g. `key-2026-08`); when set, callers must send `x-okr-key-id` |

The BFF sends its key ID via `OKR_BACKEND_SIGNING_KEY_ID` in `deploy/docker/.env`.

### Rotation steps

1. **Generate** a new secret (≥32 chars): e.g. `openssl rand -hex 32`.
2. **Verify-only deploy**: set
   - `OKR_BACKEND_SIGNING_SECRET_PREVIOUS=<old secret>`
   - `OKR_BACKEND_SIGNING_SECRET=<new secret>`
   - keep `OKR_BACKEND_SIGNING_KEY_ID` unchanged for now.

   During this window both secrets verify. The BFF still signs with the old
   secret and is accepted.
3. **Cutover**: update the BFF's `OKR_BACKEND_SIGNING_SECRET` to the new
   secret and restart `spa-bff`. Watch backend logs — there should be zero
   `Invalid request signature` entries from the BFF.
4. **Retire**: after the overlap window (recommend ≥24h), remove
   `OKR_BACKEND_SIGNING_SECRET_PREVIOUS`. Old-secret signatures are now
   rejected.

### Verification

```powershell
# During overlap: sign with OLD secret -> must be accepted
# After retirement: sign with OLD secret -> must be 401 "Invalid request signature"
```

Automated coverage: `tests/test_signing_key_rotation.py` (overlap acceptance,
unknown-ID rejection, forced-previous verification).

---

Related docs

- `docs/CONFIG_REFERENCE.md`
- `docs/DEPLOYMENT_OPERATIONS_GUIDE.md`
- `docs/DOCKER_COMPOSE.md`
- `docs/KUBERNETES.md`
- `docs/REVERSE_PROXY.md`
- `docs/TROUBLESHOOTING.md`
