# SPA BFF (`spa-bff`)

Public Backend-for-Frontend service for browser SPA clients.

Purpose:
- Expose a controlled public API surface for SPA traffic.
- Keep `backend-api` private/internal.
- Attach required internal auth/signing headers (`OKR_BACKEND_SERVICE_TOKEN`, `OKR_BACKEND_SIGNING_SECRET`) server-side only.

## Environment Variables

Required:
- `OKR_BACKEND_API_URL` (example: `http://backend-api:8100`)
- `OKR_BACKEND_SERVICE_TOKEN`

Optional:
- `OKR_BACKEND_SIGNING_SECRET` (recommended and expected in production)
- `BFF_HOST` (default: `0.0.0.0`)
- `BFF_PORT` (default: `3001`)
- `BFF_REQUEST_TIMEOUT_MS` (default: `20000`)
- `BFF_LOG_LEVEL` (default: `info`)

## Endpoints

- `GET /healthz`
- `GET|POST|PATCH|PUT|DELETE /api/backend/*`
  - Only allowlisted backend routes are proxied.
  - Non-allowlisted routes are rejected with `403`.
  - Actor-scoped routes require `X-OKR-Actor`; missing actor is rejected with `400`.
  - `POST /v1/auth/login` is the only allowlisted route that does not require actor header.

## Local Development

```bash
cd spa-bff
npm install
OKR_BACKEND_API_URL=http://127.0.0.1:8100 \
OKR_BACKEND_SERVICE_TOKEN=change-me \
OKR_BACKEND_SIGNING_SECRET=change-me \
npm run dev
```

## Tests

```bash
cd spa-bff
npm test
```
