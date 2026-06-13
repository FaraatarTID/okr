Documentation HQ: [README](../README.md)

Troubleshooting

### Runtime scope (important)

- Primary runtime and deployment path is SPA-first: `backend-api` + `backend-worker` + `spa-bff` + `spa-web`.

### Blank page or reconnecting loop

- Check reverse proxy websocket headers (Upgrade/Connection)
- Verify BASE_URL_PATH is set when using subpath hosting

### Hybrid local launcher: remote DB unreachable

- `run_hybrid_app_local.bat` now probes DB connectivity before startup.
- If remote DB DNS/TCP checks fail, launcher can auto-fallback to local SQLite:
  - Path: `tmp/okr-local-dev.sqlite3`
  - Toggle fallback: `OKR_LOCAL_DB_FALLBACK=true|false` (default `true`)
  - Reset local DB on launch: `OKR_LOCAL_DB_RESET=true|false` (default `false`)
- If fallback is disabled and remote DB is unreachable, startup stops early with a clear error.
- If your firewall blocks Postgres ports (`5432`/`6543`), test Supabase HTTPS access on `443`:
  - `python scripts/supabase_https_probe.py --url https://<project-ref>.supabase.co`
  - For authenticated REST check, set either `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_ANON_KEY`.

### Atlas Inspector does not show `Create Goal`

- On current SPA builds, `Manage Nodes` should be visible even when no node is selected.
- If you still do not see `Create Goal`:
  - Make sure you launched the SPA hybrid stack (`run_hybrid_app_local.bat`) and not a stale browser tab.
  - Fully reload the browser (`Ctrl+F5`) after pulling code updates.
  - Check `tmp/local-hybrid-logs/spa-web.err.log` for build/runtime errors.

PDF export fails

- If using PDFShift: set pdfshift_api_key in secrets
- If using Chromium mode: set `PDF_METHOD=chromium`, install Playwright, and ensure Chromium is available.
- If backend mode is enabled, verify `backend-worker` is running and has required PDF runtime access.

Runtime preflight shows configuration errors

- If preflight says `PDF_METHOD=pdfshift but PDFShift API key is missing`:
  - Add `pdfshift_api_key`
- If preflight says `PDF_METHOD=chromium but Playwright/Chromium runtime is unavailable`:
  - Install Playwright package and Chromium browser runtime.
- If preflight says unsupported `PDF_METHOD`:
  - Change `PDF_METHOD` to `pdfshift` or `chromium`
- If preflight says `OKR_BACKEND_PROXY_MUTATIONS=true but OKR_BACKEND_API_URL is not set` even after changing secrets:
  - Check the new `Config trace` info line in the UI; it shows effective value and source (`env`, `secrets_root`, `secrets_app`, `default`).
  - In secrets TOML, prefer native booleans (avoid wrapping an entire block in quotes):
    - `OKR_BACKEND_PROXY_MUTATIONS = false` (recommended)
    - `OKR_BACKEND_PROXY_MUTATIONS = "false"` (works with current parser, but not preferred)
    - `"PDF_METHOD = \"pdfshift\"\nOKR_BACKEND_PROXY_MUTATIONS=false"` (invalid TOML blob)
  - Remove/adjust any conflicting environment variable override, then restart app process.
- If strict mode is enabled (`OKR_STRICT_RUNTIME_PREFLIGHT=1`), app startup will stop on critical preflight errors until fixed.

AI features unavailable

- Run provider check: `python scripts/ai_provider_health_check.py --json`
- If using Gemini:
  - Verify `AI_PROVIDER=gemini`
  - Verify `GEMINI_API_KEY` is set and not placeholder-like
- If using self-hosted/local provider:
  - Verify `AI_PROVIDER=openai_compatible`
  - Verify `AI_BASE_URL` and `AI_MODEL` are set
  - Verify endpoint is reachable from app runtime
- If backend mode is enabled:
  - Verify `OKR_BACKEND_API_URL` is reachable from `spa-web`/`spa-bff`
  - Verify `OKR_BACKEND_SERVICE_TOKEN` matches between `spa-bff` and `backend-api`

CRUD save/update/delete errors in UI

- If backend mutation proxy is enabled (`OKR_BACKEND_PROXY_MUTATIONS=true`):
  - Verify `OKR_BACKEND_API_URL` resolves from `spa-web`/`spa-bff`
  - Verify `backend-api` is healthy (`/healthz`)
  - Verify `OKR_BACKEND_SERVICE_TOKEN` matches between services
  - If request signing is enabled, verify `OKR_BACKEND_SIGNING_SECRET` matches between `spa-bff` and `backend-api`
  - Check backend logs for 403/400 details (permission or validation failures)
- If backend is temporarily unstable, runtime remains fail-closed. Restore backend connectivity and retry; local read/mutation fallback execution is intentionally disabled.

Migrations fail

- Ensure the configured DB is reachable from the host/pod
- Check that OKR_DATABASE_URL is valid and that the user has DDL permissions
- If you see `permission denied to reassign objects`, run ownership/reassign SQL using an admin DB role; keep app runtime DSN on a least-privilege runtime role (example: `okr_app`).
  - If your current deployment uses a different least-privilege role name, use that runtime role consistently instead of `postgres`.

Workspace runtime load fails with `Multiple classes found for path "User"`

- Cause: SQLModel mapper registry/class references became stale after a code hot-reload.
- Ensure all model imports use `src.models` (no bare `models` imports).
- Ensure relationships are lambda-resolved (`sa_relationship=relationship(lambda: ...)`) instead of relying on string class lookup.
- Run guard tests:
  - `python -m pytest tests/test_models_import_consistency.py tests/test_models_relationship_resolution.py tests/test_hot_reload_model_bindings.py tests/test_hot_reload_model_rebinding.py -q`
- Restart the `spa-web` app process after a live code pull if the error loop persists.

Login not working

- Default admin only exists on an empty DB
- Check password hash path; try reset via Admin Panel after login

Supabase connection errors

- Verify OKR_DATABASE_URL uses `postgresql+psycopg2://`
- Verify host includes `supabase.com`
- Ensure `sslmode=require` is present
- Prefer transaction pooler `:6543` for runtime app traffic; avoid session-pooler saturation patterns for app workloads.
- If you see `MaxClientsInSessionMode: max clients reached`, your URL is using session mode (`:5432`); switch to transaction pooler (`:6543`).
- To enforce strict Supabase runtime URL checks at startup, set `OKR_ALLOW_NON_SUPABASE_DB=0`.
- Use overrides only for controlled exceptions:
  - `OKR_ALLOW_SUPABASE_SESSION_POOLER=1`
  - `OKR_ALLOW_SUPABASE_DIRECT_CONNECTION=1`
  - `OKR_ALLOW_SUPABASE_SUPERUSER=1`
- Confirm DB password is URL-encoded if it contains special characters

Hosting under subpath breaks assets

- Ensure proxy rewrite strips the prefix
- For SPA stack, ensure reverse-proxy base path and rewrite rules align with `spa-web` and `spa-bff` routes.

Timeouts on long interactions

- Increase proxy_read_timeout and proxy_send_timeout to >= 3600
