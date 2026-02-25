# SPA Web (`spa-web`)

Next.js frontend shell for Atlas migration.

Current phase:
- Read-first migration probe through `spa-bff`.
- Login and Atlas snapshot checks via `/api/backend/*` rewrite.
- Focus Map hierarchy and Inspector detail rendering from snapshot contracts.
- Deep-link query support for migration keys: `cycle`, `mode`, `sel`, `ft`, `lens`.
- Timer start/stop mutation probes for focused task validation.
- Inspector mutation probe for Goal/Objective/KR/Task updates via BFF (`PATCH /v1/nodes/{type}/{id}`).
- Node CRUD mutation probes for Goal/Objective/KR/Task create + delete paths via BFF.
- Guided Check-In flow (Review -> Check-Ins -> Plan) with experiment linkage/creation.
- Timeline mode with cycle-scoped Gantt visualization.

## Runtime expectations

- `spa-bff` is reachable (default local origin: `http://127.0.0.1:3001`).
- `spa-bff` has valid internal backend credentials configured.

## Environment variables

- `BFF_PUBLIC_ORIGIN` (optional, default `http://127.0.0.1:3001`)
  - Used by Next.js rewrite rule from `/api/backend/:path*` to BFF.
- `OKR_SPA_ROLLOUT_ENABLED` (optional, default `false`)
  - Enables SPA rollout gating policy.
- `OKR_SPA_ROLLOUT_ALLOW_ALL` (optional, default `false`)
  - When `true`, all authenticated users are allowed.
- `OKR_SPA_ROLLOUT_TEAM_IDS` (optional, CSV of numeric IDs)
  - Team-scoped cohort allowlist.
- `OKR_SPA_ROLLOUT_USERNAMES` (optional, CSV)
  - Username-scoped cohort allowlist.
- `OKR_SPA_ROLLOUT_ROLES` (optional, CSV, default `admin`)
  - Role-scoped cohort allowlist.
- `OKR_SPA_ROLLOUT_ALLOW_PREVIEW_BYPASS` (optional, default `false`)
  - Allows temporary `?spa_preview=1` bypass for controlled testing.

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
