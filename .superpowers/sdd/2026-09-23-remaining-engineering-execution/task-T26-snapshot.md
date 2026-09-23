Documentation HQ: [README](../../../README.md)

# T26 Control-Plane Runtime Contract — Snapshot

## Before

- Normal backend route read `main.control_plane`; `ControlPlane()` honored the ambient `OKR_CONTROL_PLANE_STATE_PATH` even though runtime templates prohibited it.
- Operator-only `POST /control-plane/environments/{environment_id}/lifecycle-events` returned 201 after appending only to the backend process-local registry.
- Current ADR text described the API as an environment inventory and lifecycle audit surface.

## After

- API list/detail read an explicit empty route-local `ControlPlane(state_path="")`; operator file data is never loaded by these routes.
- Lifecycle mutation POST is absent. Operator CLIs keep explicit file-backed lifecycle persistence.
- SQL-backed fleet rollout GET remains separate and unchanged.
- A dedicated subprocess test exercises the actual FastAPI app under a seeded operator-state env path and verifies empty list, detail 404, retired POST, operator allow, customer deny, and fleet route presence.
- Architecture, BFF boundary ADR, and customer environment contract docs state the distinction.
- OpenAPI and derived schemas/operation manifest are regenerated. Allowlist/route policy did not change because this route was never BFF-public.

## Touched implementation/test/docs/generated files

- `backend_app/routers/control_plane_routes.py`
- `tests/test_control_plane_stateless_api_contract.py`
- `tests/test_control_plane_environment_routes.py` (only obsolete API behavior expectations changed; prior T02 fixture edits preserved)
- `docs/architecture/ARCHITECTURE.md`
- `docs/bff-boundary-adr.md`
- `docs/saas/customer-environment-contract.md`
- `spa-web/src/lib/api/openapi.json`
- `spa-web/src/lib/api/generated/schema.d.ts`
- `spa-bff/src/generated/backend-schema.d.ts`
- `spa-web/src/lib/api/generated/operation-routes.ts`

## Verification summary

- Focused runtime/process/config/API tests: 57 passed.
- OpenAPI, allowlist/operation generator, mutation authorization tests: 51 passed.
- OpenAPI drift, generated type checks, allowlist/operation checks, and SPA contract boundary: pass.
- Ruff, compile, and scoped diff check: pass. Whole-file Ruff format check is blocked only by a pre-existing T02-only fixture formatting hunk, left unchanged.
