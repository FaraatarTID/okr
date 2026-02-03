Deployment guide: OKR Streamlit app

This app was originally built as a Streamlit MVP. The steps below package it for production with minimal code changes and run it behind your company domain.

Two common ways to expose it:
- Subdomain (recommended): okr.yourcompany.com
- Subpath: yourcompany.com/okr (set BASE_URL_PATH=okr)

1) Containerize the app (hardened)
- A production Dockerfile and compose file are provided in [deploy/docker/Dockerfile](deploy/docker/Dockerfile) and [deploy/docker/docker-compose.yml](deploy/docker/docker-compose.yml).
- Requirements are installed from [streamlit_app/requirements.txt](streamlit_app/requirements.txt); system dependency wkhtmltopdf is included.
- Non-root user, healthcheck, and minimal attack surface included.
- The SQLite database is persisted in a Docker volume using [deploy/docker/entrypoint.sh](deploy/docker/entrypoint.sh). No code changes required.

Build and run (on a server with Docker):
- Copy [deploy/docker/.env.example](deploy/docker/.env.example) to .env and adjust ports and BASE_URL_PATH if using a subpath.
- From the deploy/docker folder:
  - docker compose up -d --build
- App will listen on HOST_PORT (default 8501). Test at http://SERVER:8501

2) Reverse proxy and domain (HTTPS)
- Put the app behind Nginx (or Caddy/Traefik) on your corporate host.
- An example Nginx config is provided in [deploy/nginx.conf](deploy/nginx.conf):
  - Subdomain: proxy / to the container’s port
  - Subpath: also set BASE_URL_PATH=okr in compose and use the /okr location block
- Add TLS with your corporate certificate or Certbot.

3) Secrets and API keys
- If the app uses Streamlit secrets (e.g., PDFShift, Google APIs), mount a secrets file into the container:
  - Create deploy/secrets/secrets.toml (do not commit it)
  - Mount it in compose by uncommenting the secrets volume line so it appears at /app/streamlit_app/.streamlit/secrets.toml
- Alternatively, map environment variables and read them in code where supported.

4) Database and migrations
- The app uses SQLite at streamlit_app/okr_database.db.
- Migrations (Alembic) run on startup via code in [streamlit_app/src/database.py](streamlit_app/src/database.py).
- Data is persisted in a Docker named volume (okr_data). Back up by "docker run --rm -v okr_data:/data alpine tar -czf - /data > backup.tar.gz".

5) Running under a subpath
- Use a reverse proxy rule that strips the prefix and set BASE_URL_PATH in the container.
- Example: BASE_URL_PATH=okr, proxy /okr/ to http://127.0.0.1:8501/ with a rewrite to remove /okr/.

6) Windows service (alternative to Docker)
- If you prefer not to use Docker on Windows, run Streamlit as a Windows Service and put IIS/NGINX in front:
  - Install Python 3.11 and dependencies from requirements.txt
  - Create a Windows Service with NSSM (Non-Sucking Service Manager):
    - Path: python.exe
    - Args: -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
    - Working dir: streamlit_app
  - Reverse proxy from IIS/NGINX to http://127.0.0.1:8501

7) Health checks and restarts
- Compose sets restart: unless-stopped. The image has an HTTP healthcheck. Integrate with your platform’s observability (e.g., Prometheus/nginx logs, uptime monitors).

8) Upgrades and migrations
- Pull latest code, rebuild the image, and recreate the container:
  - docker compose pull || true
  - docker compose up -d --build
- Alembic migrations run automatically on app start.

Notes
- This keeps the application code unchanged. Operational settings are provided via container args and the reverse proxy.
- For subpath hosting, Streamlit requires the baseUrlPath flag (already supported by the container CMD).

Appendix A: CI/CD (GitHub Actions)
- A workflow is included: [\.github/workflows/docker-deploy.yml](.github/workflows/docker-deploy.yml)
  - Builds and pushes image to GHCR on push to main/master
  - Optional remote deployment to a Docker Compose host via SSH (configure secrets: SSH_HOST, SSH_USER, SSH_KEY, REMOTE_DEPLOY_DIR)

Appendix B: Kubernetes (optional)
- Manifests in [deploy/k8s](deploy/k8s): Deployment (1 replica), Service, Ingress with TLS via cert-manager, and a PVC for SQLite.
- Because SQLite is a single-writer DB, keep replicas=1. For multi-user scale, consider migrating to a network database (e.g., Postgres) in a later phase.

Appendix C: Upgrade storage beyond Google Drive/SQLite
- Switch to PostgreSQL with no code changes:
  - Provide a database URL via env OKR_DATABASE_URL or DATABASE_URL, or via [streamlit secrets] [database.url].
  - The app and Alembic will use that URL automatically.
- With Docker Compose, bring up Postgres and point the app to it:
  - cp deploy/docker/.env.example deploy/docker/.env
  - docker compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.postgres.yml up -d --build
  - The override adds a postgres:16 service and sets OKR_DATABASE_URL for the app.
- Initial data migration from Google Sheets:
  - In the app, use the existing Sheets restore (Sync → Restore) to pull all data into the new DB; it uses the same session, so it will load into Postgres when configured.
  - Alternatively, export current SQLite and import into Postgres with standard tools if needed. For most MVPs, a one-time restore from Sheets is sufficient.
 
Further reading (comprehensive docs)
- Configuration reference: [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)
- Deployment checklist: [docs/DEPLOY_CHECKLIST.md](docs/DEPLOY_CHECKLIST.md)
- Docker Compose guide: [docs/DOCKER_COMPOSE.md](docs/DOCKER_COMPOSE.md)
- Kubernetes guide: [docs/KUBERNETES.md](docs/KUBERNETES.md)
- Reverse proxy guide: [docs/REVERSE_PROXY.md](docs/REVERSE_PROXY.md)
- Operations: [docs/OPERATIONS.md](docs/OPERATIONS.md)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md)
