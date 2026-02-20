Documentation HQ: [README](../README.md)

Troubleshooting

Blank page or reconnecting loop
- Check reverse proxy websocket headers (Upgrade/Connection)
- Verify BASE_URL_PATH is set when using subpath hosting

PDF export fails
- If using PDFShift: set pdfshift_api_key in secrets
- Ensure `PDF_METHOD=pdfshift`
- If backend mode is enabled, verify `backend-worker` is running and has access to `PDFSHIFT_API_KEY`

Runtime preflight shows configuration errors
- If preflight says `PDF_METHOD=pdfshift but PDFShift API key is missing`:
  - Add `pdfshift_api_key`
- If preflight says unsupported `PDF_METHOD`:
  - Change `PDF_METHOD` to `pdfshift`
- If strict mode is enabled (`OKR_STRICT_RUNTIME_PREFLIGHT=1`), app startup will stop on critical preflight errors until fixed.

AI features unavailable
- Run provider check: `python streamlit_app/scripts/ai_provider_health_check.py --json`
- If using Gemini:
  - Verify `AI_PROVIDER=gemini`
  - Verify `GEMINI_API_KEY` is set and not placeholder-like
- If using self-hosted/local provider:
  - Verify `AI_PROVIDER=openai_compatible`
  - Verify `AI_BASE_URL` and `AI_MODEL` are set
  - Verify endpoint is reachable from app runtime
- If backend mode is enabled:
  - Verify `OKR_BACKEND_API_URL` is reachable from `okr`
  - Verify `OKR_BACKEND_SERVICE_TOKEN` matches between `okr` and `backend-api`

Migrations fail
- Ensure the configured DB is reachable from the host/pod
- Check that OKR_DATABASE_URL is valid and that the user has DDL permissions

Login not working
- Default admin only exists on an empty DB
- Check password hash path; try reset via Admin Panel after login

Supabase connection errors
- Verify OKR_DATABASE_URL uses `postgresql+psycopg2://`
- Verify host includes `supabase.com`
- Ensure `sslmode=require` is present
- Confirm DB password is URL-encoded if it contains special characters

Hosting under subpath breaks assets
- Ensure proxy rewrite strips the prefix
- Ensure Streamlit CLI flag --server.baseUrlPath is set (container CMD handles this)

Timeouts on long interactions
- Increase proxy_read_timeout and proxy_send_timeout to >= 3600
