Documentation HQ: [README](../README.md)

Docker Compose deployment

Single host, subdomain (recommended)
- Copy deploy/docker/.env.example to deploy/docker/.env
- Ensure PORT and HOST_PORT are set; leave BASE_URL_PATH empty
- Build and start services using the base compose file
- Put Nginx in front using deploy/nginx.conf (add TLS)

Single host, subpath
- Set BASE_URL_PATH to the desired path (e.g., okr)
- Use the subpath location in deploy/nginx.conf (with rewrite removing the prefix)

Starting with PostgreSQL
- Preferred: managed Postgres (RDS/Azure/GCP)
  - Set OKR_DATABASE_URL in the environment (compose env or .env)
- Alternative: local Postgres service
  - Use the override file deploy/docker/docker-compose.postgres.yml
  - It adds a postgres:16 service and wires OKR_DATABASE_URL for the app

Secrets
- Create a secrets file if using integrations and mount as:
  - /app/streamlit_app/.streamlit/secrets.toml
- Use deploy/secrets/secrets.toml.example as a template

Persistence
- App volume okr_data stores the SQLite DB if fallback is used
- With Postgres, data is in the DB; ensure DB backups are enabled

Health & logs
- Health: GET / should return 200
- Logs: docker compose logs okr

Upgrades
- Pull code/image; rebuild if needed; restart compose services

Rollback
- Recreate container with previous image tag
