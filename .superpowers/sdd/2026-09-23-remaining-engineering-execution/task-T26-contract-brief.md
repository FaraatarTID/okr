Documentation HQ: [README](../../../README.md)

# T26 Control-Plane Runtime Contract — Read-Only Packet Brief

Date: 2026-09-23  
Status: proposed scope for coordinator ruling; no implementation changes made.

## Canonical scope

The authoritative A4 row in `docs/REMAINING_ENGINEERING_PLAN.md` permits either a durable, contract-compliant store or a read-only/stateless API whose lifecycle metadata remains in operator state files. The execution plan selects **stateless/read-only; do not add persistence**. Current runtime construction is `backend_app/main.py` `control_plane = ControlPlane()`; provisioning/release/backup CLIs persist through the explicit operator file `tmp/saas-control-plane.json`; normal runtime templates and process-contract checks prohibit `OKR_CONTROL_PLANE_STATE_PATH`.

## Proposed exact route decision

- Keep `GET /control-plane/environments` and `GET /control-plane/environments/{environment_id}` as authenticated operator-only, process-local inventory reads. In the normal backend process they return an empty list / 404 because that process has no durable operator registry. Document the boundary as explicitly ephemeral and non-authoritative; operator CLI state files remain the recorded lifecycle source.
- **Remove `POST /control-plane/environments/{environment_id}/lifecycle-events` from the backend API.** It only appends to the backend process's memory by default, so a 201 response implies an audit record that disappears on restart and is not the operator-file record. The operator CLIs retain their explicit file-backed lifecycle operations; this packet must not add an alternate API persistence path.
- Keep `GET /control-plane/v1/rollouts/{rollout_id}` unchanged: it reads the separately configured SQL fleet control plane and is not the `ControlPlane()` in-memory registry.
- Reject `OKR_CONTROL_PLANE_STATE_PATH` in runtime templates/process contract as today. Do not change operator CLI explicit `state_path` support.

This is the narrowest interpretation of the selected “stateless/read-only API surface.” No in-repository production caller of the lifecycle-events route was found; current references are its route test. Removing the route changes OpenAPI and therefore needs one coordinated contract-artifact steward pass, even though the route is not BFF-public.

## Acceptance behavior

1. A runtime contract test sets `OKR_CONTROL_PLANE_STATE_PATH` to a file containing a recorded environment, constructs/loads the normal API runtime, and proves the environment is not served from that file; normal `/control-plane/environments` is empty and its detail is 404. The same runtime has no durable lifecycle-event write route (POST returns 404/405).
2. An authenticated operator can still use the two inventory GETs; a customer principal is denied; existing SQL fleet rollout GET remains covered and operator-only.
3. Operator CLI persistence tests remain green, proving the explicit state file remains useful to the operator workflow and is not silently retired.
4. `verify_process_contract.py` and environment-config tests continue to reject the persistent-state env var in normal runtime templates; a new/updated contract assertion makes this choice explicit.
5. Architecture/SaaS boundary docs say inventory API is ephemeral/non-authoritative, lifecycle source is operator CLI state, and fleet rollout SQL reads are separate. Historical `docs/architecture-status.md` should remain historical; do not rewrite its dated implementation narrative.
6. OpenAPI export, generated SPA/BFF API declarations, allowlist and operation manifest checks are run once by the contract steward; verify the lifecycle POST is absent from exported OpenAPI and generated artifacts.

## Proposed owned files and lane constraints

**T26 implementation/test/doc scope:**

- `backend_app/routers/control_plane_routes.py` — remove lifecycle mutation route.
- `tests/test_control_plane_stateless_runtime.py` — add runtime/API stateless assertions (or add a new dedicated `tests/test_control_plane_stateless_api_contract.py`; do not edit the shared route test without coordination).
- `scripts/verify_process_contract.py` and `tests/test_process_contract.py` — only if strengthening the static process-contract rule is needed; current env-template rejection already exists.
- `tests/test_saas_environment_config.py` — preserve/strengthen existing prohibition assertion.
- `docs/architecture/ARCHITECTURE.md`, `docs/bff-boundary-adr.md`, and `docs/saas/customer-environment-contract.md` — align the current control-plane description with this choice. `docs/saas/twelve-factor-evidence.md` already describes operator-process opt-in persistence and should only change if wording is found inconsistent.

**Shared generated contract files reserved to one steward after route change:** `spa-web/src/lib/api/openapi.json`, `spa-web/src/lib/api/generated/schema.d.ts`, `spa-bff/src/generated/backend-schema.d.ts`, generated operation-routes/allowlist files if the generators change them. Do not hand-edit. `/control-plane/...` is not a route-policy entry today; retain that exclusion.

**Explicit exclusions:** `backend_app/main.py` (currently shared/dirty under T02/T08), `tests/test_control_plane_environment_routes.py` (currently dirty under T02; contains route/fake-main test edits), `docs/REMAINING_ENGINEERING_PLAN.md` and `.superpowers/sdd/.../progress.md` (coordinator-owned), historical `docs/architecture-status.md`, durable persistence implementation, SQL control-plane schema, CLI state format, and customer-domain routes.

## Conflict scan

- Plan overlap table explicitly names `T19 ↔ T23 ↔ T26` over backend routers/schemas, OpenAPI, generated clients, allowlist/auth matrix; one steward runs the full contract chain.
- T08 claims `backend_app/main.py` and excludes routes outside its exact typing slice. Current dirty `backend_app/main.py` includes response-scope compatibility edits; avoid it.
- `tests/test_control_plane_environment_routes.py` has existing uncommitted T02 edits (principal fixture typing and list annotation). Avoid it or coordinate a serialized merge.
- `scripts/verify_process_contract.py`, `tests/test_process_contract.py`, `tests/test_saas_environment_config.py`, route implementation, architecture, ADR and customer-environment docs were clean in the inspected worktree; generated OpenAPI files were not listed dirty.
- Existing `docs/bff-boundary-adr.md` calls the API an “inventory and lifecycle audit metadata” boundary; if the POST is removed, revise that current description. `docs/architecture-status.md` contains dated historical statements of durable API behavior; preserve as history rather than silently rewriting it.

## Coordinator decision requested

Approve/revise the exact POST-route retirement above and assign the generated OpenAPI sequence to one named steward before implementation. If compatibility requires retaining POST, the API cannot honestly be called read-only/stateless while returning 201 for a process-memory audit append; the scope would need an explicit alternate response/route contract and tests.
