# SPA Web (`spa-web`)

Documentation HQ: [README](../README.md)

Next.js frontend shell for Atlas migration.

Boundary ownership:
- Owns rendering, browser state, feature workflows, and generated API client
  consumption.
- Calls `spa-bff` through browser-facing session and backend proxy routes.
- Does not hold backend credentials, access the database, or implement backend
  authorization rules.
- Backend/domain changes belong in `backend_app/` or shared `src/` modules.

Current phase:
- Read-first migration probe through `spa-bff`.
- Login and Atlas snapshot checks via Next.js API route proxy (`/api/backend/*` -> `spa-bff`).
- Focus Map hierarchy and Inspector detail rendering from snapshot contracts.
- Deep-link query support for migration keys: `cycle`, `mode`, `sel`, `ft`, `lens`.
- Timer start/stop mutation probes for focused task validation.
- Inspector mutation probe for Goal/Objective/KR/Task updates via BFF (`PATCH /v1/nodes/{type}/{id}`).
- Node CRUD mutation probes for Goal/Objective/KR/Task create + delete paths via BFF.
- Guided Check-In flow (Review -> Check-Ins -> Plan) with experiment linkage/creation.
- Timeline mode with cycle-scoped Gantt visualization.
- **Unified AI Analysis**: single button auto-analyzes all KRs in scope.
- **Task progress auto-compute**: progress computed from `total_time_spent / estimated_minutes * 100`.
- **Modal Inspector/Manage Nodes**: clicking entities in Focus Map opens Inspector or Manage Nodes as popup modals.

## API client layout

- `src/lib/api.ts` is a compatibility barrel for callers.
- Domain modules hold implementation:
  - `src/lib/api/auth.ts`
  - `src/lib/api/atlas.ts`
  - `src/lib/api/admin.ts`
  - `src/lib/api/ritual.ts`
- `src/lib/api/jobs.ts`
- shared helpers in `src/lib/api/http.ts`

Generated contract types are refreshed at repository scope with
`just generate-api`. The generated declarations are consumed as type-only
aliases; runtime requests still go through the BFF boundary.

## Runtime expectations

- `spa-bff` is reachable (default local origin: `http://127.0.0.1:3001`).
- `spa-bff` has valid internal backend credentials configured.

## Environment variables

- `BFF_PUBLIC_ORIGIN` (optional, default `http://127.0.0.1:3001`)
  - Used by server-side route handlers to proxy `/api/backend/*` and `/api/session/*` to BFF.
- `NEXT_PUBLIC_OKR_AI_SYNC_MAX_DELTA` (optional, default `100`)
  - Maximum KR point change allowed per AI sync run.
- `NEXT_PUBLIC_OKR_AI_SYNC_ALLOW_DECREASE` (optional, default `true`)
  - Allow AI to lower KR progress values. Set to `false` to only allow increases.

## Local development

```bash
cd spa-web
npm install
npm run dev
```

Open:
- `http://127.0.0.1:3000`

## Build

```bash
cd spa-web
npm run build
```

## Frontend tests

```bash
cd spa-web
npm test
```
