Troubleshooting

Blank page or reconnecting loop
- Check reverse proxy websocket headers (Upgrade/Connection)
- Verify BASE_URL_PATH is set when using subpath hosting

PDF export fails
- If using pdfkit: wkhtmltopdf must be installed (already in container)
- If using PDFShift: set pdfshift_api_key in secrets

Migrations fail
- Ensure the configured DB is reachable from the host/pod
- Check that OKR_DATABASE_URL is valid and that the user has DDL permissions

Login not working
- Default admin only exists on an empty DB
- Check password hash path; try reset via Admin Panel after login

Google Sheets sync unavailable
- Provide gcp_service_account in secrets and GCP_SPREADSHEET_NAME if needed
- Without secrets, sync is disabled by design

Hosting under subpath breaks assets
- Ensure proxy rewrite strips the prefix
- Ensure Streamlit CLI flag --server.baseUrlPath is set (container CMD handles this)

Timeouts on long interactions
- Increase proxy_read_timeout and proxy_send_timeout to >= 3600
