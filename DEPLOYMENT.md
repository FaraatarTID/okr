Documentation HQ: [README](README.md)

Enterprise Deployment Guide (Step-by-Step, Beginner Friendly)

Last updated: 2026-02-16

This guide is for deploying the OKR app in a company environment where users access it through a corporate URL such as:
- `https://okr.mycompany.com` (recommended)
- `https://mycompany.com/okr` (supported)

If you are not sure what to choose, use this default stack:
- Docker Compose
- Supabase PostgreSQL
- Nginx reverse proxy
- HTTPS (TLS certificate)

This is the safest and easiest enterprise path for this repo.

---

What this deployment gives you
- Non-root container runtime
- Automatic DB migrations at app startup
- Health checks and restart policy
- Reverse-proxy compatible with Streamlit websocket traffic
- Optional CI/CD via GitHub Actions

Key files used by this guide
- `deploy/docker/Dockerfile`
- `deploy/docker/docker-compose.yml`
- `deploy/docker/.env.example`
- `deploy/docker/.env.mycompany.example`
- `deploy/nginx.conf`
- `deploy/nginx.okr.mycompany.com.conf`
- `deploy/secrets/secrets.toml.example`
- `.github/workflows/docker-deploy.yml`

---

Quick decision matrix

1) Which URL structure?
- Use subdomain if possible: `okr.mycompany.com`
- Use subpath only if your company policy requires it: `mycompany.com/okr`

2) Which database?
- Required: Supabase PostgreSQL (Session Pooler URL with `sslmode=require`)

3) Which platform?
- Start with Docker Compose on one VM
- Use Kubernetes only if your team already runs K8s operationally

---

Deployment modes (important)

Use one of these modes:

1) Streamlit Cloud (MVP/simple hosting)
- No SSH deploy secrets are required.
- The app is deployed by Streamlit Cloud from your GitHub repo.
- In this mode, the GitHub Actions SSH deploy step is expected to skip.

2) Docker Compose on your own server (enterprise/self-hosted)
- SSH deploy is disabled by default. Set `ENABLE_SSH_DEPLOY=true` (repo secret or variable) before adding SSH deploy secrets.
- Use this when you want GitHub Actions to connect to your server and run `docker compose`.

---

Path A (recommended): Docker Compose + Postgres + Nginx + TLS

Use this if you want the fastest reliable enterprise deployment.

Step 0: Collect required values

Prepare these values first:
- `APP_DOMAIN`: for example `okr.mycompany.com`
- `SERVER_IP`: public/private server IP
- `OKR_DATABASE_URL`: example `postgresql+psycopg2://postgres.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require`
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
PORT=8501
HOST_PORT=8501
BASE_URL_PATH=
OKR_DATABASE_URL=postgresql+psycopg2://postgres.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require

# Optional image pin (recommended after first stable release)
# IMAGE=ghcr.io/your-org/okr-streamlit:2026-02-14
```

Notes:
- Keep `BASE_URL_PATH` empty for subdomain hosting.
- For subpath hosting (`/okr`), set `BASE_URL_PATH=okr`.

Step 4: Configure optional secrets (PDF/API integrations)

```bash
mkdir -p deploy/secrets
cp deploy/secrets/secrets.toml.example deploy/secrets/secrets.toml
```

Then edit `deploy/secrets/secrets.toml` with your real keys if needed.
Do not commit this file.

Step 5: Start the application

From repo root:

```bash
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

Health check:

```bash
docker compose -f deploy/docker/docker-compose.yml ps
curl -I http://127.0.0.1:8501/
```

Expected:
- Container status is `Up` (eventually healthy)
- HTTP response from `/` is `200 OK`

Step 6: Configure Nginx reverse proxy

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
        proxy_pass http://127.0.0.1:8501/;
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

Step 7: Create DNS record

In your DNS provider:
- Add `A` record: `okr.mycompany.com -> SERVER_IP`

Wait for propagation and confirm:

```bash
nslookup okr.mycompany.com
```

Step 8: Enable HTTPS (TLS)

Using Certbot (public CA):

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d okr.mycompany.com -m your-email@company.com --agree-tos --redirect --non-interactive
```

If your company uses internal PKI, install certificates per your security policy instead of Certbot.

Step 9: First login and hardening

On first run with empty DB:
- Default login is `admin / admin`
- You will be forced to change password

Immediately after login:
1. Change admin password to a strong one.
2. Create named admin accounts for real admins.
3. Disable unused accounts.
4. Create initial OKR cycle.
5. Verify role-based access for manager/member users.

Step 10: Validate production readiness

Run these checks:

```bash
# App reachable over HTTPS
curl -I https://okr.mycompany.com

# Container logs
docker compose -f deploy/docker/docker-compose.yml logs --tail=200 okr

# Confirm proxy configuration active
sudo nginx -t
```

Confirm manually:
- Login works
- Create Goal/Objectives/KRs/Tasks
- Timer starts/stops
- Reports load
- No websocket reconnect loops in browser

---

Path B: Kubernetes (for teams already running K8s)

Use manifests in `deploy/k8s`.

High-level sequence:
1. Create namespace `okr`.
2. Create DB secret (`OKR_DATABASE_URL`) from `deploy/k8s/secret-db.yaml`.
3. Apply deployment/service/ingress.
4. Set ingress host/TLS secret.
5. Verify readiness/liveness and HTTPS.

Important:
- Streamlit sessions are stateful, so use sticky sessions at ingress when scaling.

Detailed docs:
- `docs/KUBERNETES.md`

---

Operations (day 2)

Logs

```bash
docker compose -f deploy/docker/docker-compose.yml logs -f okr
```

Restart app

```bash
docker compose -f deploy/docker/docker-compose.yml restart okr
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
- Block direct public access to `8501`.
- Keep secrets in `deploy/secrets/secrets.toml` or platform secret manager.
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
- Ensure `OKR_DATABASE_URL` is set and points to `*.supabase.com` with `postgresql+psycopg2://`.

Cannot log in:
- If DB is new, use `admin/admin` once and change password.
- If DB is existing, default admin bootstrap does not run again.

---

CI/CD option (GitHub Actions)

Workflow file:
- `.github/workflows/docker-deploy.yml`

What it can do:
- Build and push image to GHCR on push to `main`/`master`
- Optional remote deploy over SSH (self-hosted mode only, opt-in via `ENABLE_SSH_DEPLOY=true`)

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

If you are using Streamlit Cloud and not SSH deploy:
- Keep `ENABLE_SSH_DEPLOY` unset (or `false`).
- Do not set SSH deploy secrets.
- The SSH deploy job should be skipped automatically.

Tip:
- Use immutable image tags for controlled rollback.

Security note:
- Never commit private keys or any deploy secrets to the repository.

---

Related docs
- `docs/CONFIG_REFERENCE.md`
- `docs/DEPLOY_CHECKLIST.md`
- `docs/DOCKER_COMPOSE.md`
- `docs/KUBERNETES.md`
- `docs/REVERSE_PROXY.md`
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
- `docs/RUNBOOK.md`
