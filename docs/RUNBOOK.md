Documentation HQ: [README](../README.md)

Runbook: first deployment

1) Build and publish image (optional if using local build)
- Use the provided GitHub Actions workflow or build locally.

2) Choose deployment path
- Docker Compose on a single VM (recommended to start)
- Kubernetes in a cluster (optional)

3) Configure environment
- Provide OKR_DATABASE_URL for Postgres (managed DB recommended)
- Decide hosting scheme: subdomain vs subpath
- Configure reverse proxy with TLS and websocket support
- (Recommended) Set PRODUCTION=true to disable Sheets sync and enforce a non-SQLite database

4) Start services
- Compose: start app (and Postgres if not managed)
- K8s: apply manifests

5) Post-deploy checks
- Health check: GET /
- Login as admin/admin and change password
- Create your first cycle and users

6) Enable optional integrations
- Add secrets.toml for PDFShift or Google sheets if required

7) Set up backups and monitoring
- Automated DB backups
- Uptime checks on the proxy endpoint
- Log retention for proxy and app
