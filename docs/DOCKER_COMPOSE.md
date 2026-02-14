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
- Required: Supabase PostgreSQL
  - Set OKR_DATABASE_URL in the environment (compose env or .env)
  - Use the session pooler URL with `sslmode=require`

Secrets
- Create a secrets file if using integrations and mount as:
  - /app/streamlit_app/.streamlit/secrets.toml
- Use deploy/secrets/secrets.toml.example as a template

Persistence
- All runtime data is stored in Supabase PostgreSQL
- Ensure DB backups are enabled

Health & logs
- Health: GET / should return 200
- Logs: docker compose logs okr

Upgrades
- Pull code/image; rebuild if needed; restart compose services

Rollback
- Recreate container with previous image tag
