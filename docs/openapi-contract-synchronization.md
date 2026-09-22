# OpenAPI Contract Synchronization

Documentation HQ: [README](../README.md)

## Purpose

`backend_app` OpenAPI is the sole contract authority for the browser-facing
application path:

```text
backend_app OpenAPI -> committed OpenAPI artifact -> generated SPA/BFF types
                                      |                    |
                                      +-> BFF policy ------+
```

The SPA does not call `backend_app` directly. Browser requests travel through
`spa-web` to `spa-bff`, and the BFF proxies only the documented, allowlisted
backend operations. The BFF retains ownership of its public login and session
endpoints; those BFF-owned response DTOs are intentionally local, while its
backend login/session calls use generated backend types.

## Contract artifacts

| Artifact | Owner and role | Do not edit by hand |
|---|---|---|
| `spa-web/src/lib/api/openapi.json` | Committed backend OpenAPI artifact | Yes; export it from `backend_app` |
| `spa-web/src/lib/api/generated/schema.d.ts` | SPA OpenAPI declarations | Yes |
| `spa-bff/src/generated/backend-schema.d.ts` | BFF OpenAPI declarations | Yes |
| `spa-web/src/lib/api/generated/operation-routes.ts` | Generated operation ID, method, path, and BFF-public route manifest | Yes |
| `spa-bff/src/allowlist.ts` | Generated method/path policy with OpenAPI operation IDs | Yes |
| `spa-bff/src/route-policy.json` | Reviewed policy metadata: routes, methods, and actor requirement | No; update deliberately when exposing a new route |

The generated SPA facade in `spa-web/src/lib/api/backend-schema.ts` exposes
operation-level bodies, success responses, documented errors, query/path
parameters, no-content responses, and binary responses. It is the type bridge
used by the typed transport in `spa-web/src/lib/api/http.ts`.

## Changing a backend API contract

When changing a router, request model, response model, success media type, or
operation exposure:

1. Export the backend schema and regenerate both TypeScript declarations.
2. Regenerate the BFF allowlist and SPA operation manifest.
3. Update a BFF policy entry only when the operation should be browser-public.
   Internal/operator routes remain absent from `route-policy.json`.
4. Convert or update the SPA wrapper through an operation-typed helper.
5. Add behavior and type-level coverage for the changed operation.

Run the complete local sequence from the repository root:

```bash
python scripts/export_openapi.py
npm --prefix spa-web run gen:api
npm --prefix spa-bff run gen:api
python scripts/generate_bff_allowlist.py
python scripts/generate_spa_operation_routes.py

python scripts/check_openapi_drift.py
python scripts/generate_bff_allowlist.py --check
python scripts/generate_spa_operation_routes.py --check
python scripts/check_spa_api_contract_boundary.py
npm --prefix spa-web run check:gen:api
npm --prefix spa-bff run check:gen:api
```

`just generate-api` remains a convenient repository generation entry point;
run the explicit checks above before submitting a contract change.

## SPA transport rules

`backendJsonRequest`, `retryBackendJsonRequest`, `backendNoContentRequest`, and
`backendBlobRequest` infer the HTTP method, allowed URL shape, request body,
query parameters, and successful response category from an OpenAPI operation
ID. A wrapper cannot use an operation that is not BFF-public.

- Use `backendJsonRequest` for documented JSON success responses.
- Use `backendNoContentRequest` for documented `204`/`205` success responses;
  it never parses an empty body as JSON.
- Use `backendBlobRequest` only for a documented non-JSON success response.
  At present this is the admin database export.
- Keep UI-only transformations explicit and local. For example, the audit
  screen projects the generic generated read-query payload into a defensive
  view model; it does not declare a second backend response schema.

The database backup endpoint is deliberately a binary download:
`GET /v1/admin/db-backup` documents and returns
`application/octet-stream` plus a `Content-Disposition` attachment filename.
The BFF forwards the browser `Accept` preference and preserves the binary
bytes and download headers.

## Boundary and CI enforcement

`scripts/check_spa_api_contract_boundary.py` rejects production SPA fetches
outside the typed transport (apart from the named BFF session/proxy boundary),
legacy `backendFetch`, undocumented operation IDs, and hand-authored exported
backend `*Response` contracts. It also detects direct and bracket-notation
fetch aliases such as `globalThis["fetch"]`.

The `contracts-quality` GitHub Actions job runs all OpenAPI, generator, and
boundary checks when any of these contract inputs change:

- `backend_app/**`;
- `spa-web/src/lib/api/**`;
- `spa-bff/src/**`;
- OpenAPI/contract checking and generation scripts.

This is intentionally more precise than running the contract job for every
frontend change, while ensuring an OpenAPI source change cannot leave SPA or
BFF generated declarations stale.

## Required verification

For a contract change, run the generation checks above plus:

```bash
npm --prefix spa-web run typecheck
npm --prefix spa-web run test
npm --prefix spa-bff run typecheck
npm --prefix spa-bff test
python -m pytest tests/test_spa_api_contract_boundary.py \
  tests/test_generate_bff_allowlist.py \
  tests/test_generate_spa_operation_routes.py
```

CI additionally runs the affected runtime, frontend, and required aggregate
status checks. A stale artifact, a missing OpenAPI operation mapping, a direct
untyped backend fetch, or an undocumented BFF route must fail before merge.
