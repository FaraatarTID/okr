Documentation HQ: [README](../README.md)

Operations guide

First run
- App runs migrations automatically
- Default admin admin/admin is created; change password immediately

Backups
- Supabase PostgreSQL: enable automated backups/snapshots and test restore

Monitoring
- Uptime check: GET /
- Reverse proxy logs (Nginx) for access and errors
- Container logs for app messages

Upgrades
- Compose: pull new image, up -d --build
- K8s: update image tag, rollout status

Secrets management
- Store DB credentials and API keys in secrets (not in repo)
- Rotate credentials periodically

Security hardening
- TLS everywhere
- Limit exposed ports (only proxy exposed)
- Non-root containers (already configured)
- Set firewall rules so only the proxy can reach the app port
- Keep DB credentials in secret manager and rotate regularly

Incident response
- Take snapshots before risky changes
- Know rollback steps for Compose and K8s
