Deployment checklist

Pre-requisites
- DNS entry prepared (subdomain preferred, e.g., okr.company.com)
- TLS certificate method selected (corporate CA, Certbot, or managed ingress)
- Host with Docker (or Kubernetes cluster) available
- Postgres endpoint and credentials (for professional DB start)

Application image
- Build/push image via CI (recommended) or locally
- Confirm image runs: app starts and serves on PORT

Configuration
- Choose hosting mode: subdomain (recommended) or subpath
- Decide BASE_URL_PATH (empty for subdomain; short slug for subpath)
- Provide OKR_DATABASE_URL for Postgres
- Prepare Streamlit secrets file (if using PDFShift/Google integrations)
- (Recommended) Enable PRODUCTION=true to disable Sheets sync and require a non-SQLite database

Reverse proxy
- Configure Nginx/Caddy/Traefik to:
  - Terminate TLS
  - Proxy websocket connections
  - Set timeouts to >= 3600 seconds
  - Preserve Host, X-Forwarded-Proto, and upgrade headers

Compose deployment
- Create deploy/docker/.env from template
- For Postgres:
  - Use the compose override file with a managed DB URL or bundled postgres service
- Run compose and verify health on /

Kubernetes deployment (optional)
- Create namespace okr
- Create secret okr-db with OKR_DATABASE_URL
- Apply deployment, service, and ingress
- Verify TLS and health on /

First-run
- Log in as admin/admin
- Change admin password
- Create initial OKR cycle
- Create users and assign roles

Operations
- Configure backups (Postgres automated snapshots)
- Enable metrics/monitoring on reverse proxy and container runtime
- Document uptime checks
