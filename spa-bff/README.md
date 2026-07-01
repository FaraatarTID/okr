# SPA BFF (`spa-bff`)

Documentation HQ: [README](../README.md)

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
- `BFF_REQUEST_TIMEOUT_MS` (default: `120000`)
- `BFF_SESSION_SECRET` (required in non-development runtime)
- `BFF_SESSION_TTL_SECONDS` (default: `28800`)
- `BFF_COOKIE_SECURE` (default: `true` outside development)
- `BFF_LOG_LEVEL` (default: `info`)

## Endpoints

- `GET /healthz`
- `POST /session/login`
- `GET /session/me`
- `POST /session/logout`
- `GET|POST|PATCH|PUT|DELETE /api/backend/*`
  - Only allowlisted backend routes are proxied.
  - Non-allowlisted routes are rejected with `403`.
  - Actor-scoped routes require a valid BFF session cookie; missing/invalid session is rejected with `401`.
  - Actor identity is derived from session state and forwarded server-side.
  - Client-supplied `X-OKR-Actor` is ignored for actor-scoped routes.
  - `POST /v1/auth/login` is the only allowlisted route that does not require actor header.

## Local Development

```bash
cd spa-bff
npm install
OKR_BACKEND_API_URL=http://127.0.0.1:8100 \
OKR_BACKEND_SERVICE_TOKEN=change-me \
OKR_BACKEND_SIGNING_SECRET=change-me \
BFF_SESSION_SECRET=change-me \
npm run dev
```

## Tests

```bash
cd spa-bff
npm test
```
