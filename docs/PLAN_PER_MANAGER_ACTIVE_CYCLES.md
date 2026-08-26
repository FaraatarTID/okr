# Per-Manager Active Cycles — Comprehensive Plan

Documentation HQ: [README](README.md)

Status: **CLOSED (implemented, deployed, and verified)**
Date: 2026-08-26
Supersedes: the single-global-active-cycle invariant documented in ARCHITECTURE.md and enforced by migrations `z3a4b5c6d7e8` / `a4b5c6d7e8f9`.

---

## 1) Approved design decisions

| Decision | Choice |
|---|---|
| D1: Legacy unowned cycles (`owner_manager_id IS NULL`) | Backfilled to admin ownership |
| D2: Admin-owned active cycles | Visible to **everyone** (global cycle) |
| D3: Manager panel access | Managers get the **Cycles panel only** (not Users/Teams/Security/Backup/Audit) |
| D4: Teams handling | Deferred. Team membership stays a data field with no functional effect |

## 2) Target model

Each cycle has exactly one owner (`owner_manager_id`, NOT NULL after backfill).
At most **one active cycle per owner**:

```
UNIQUE (owner_manager_id) WHERE is_active = true
```

Visibility:
- **Admin**: all cycles.
- **Manager**: own cycles + admin-owned (global) cycles.
- **Member**: their manager's cycles + admin-owned (global) cycles.

Effective cycle resolution:
- **Admin**: explicit `cycle_id`, or highest-id active cycle as default.
- **Manager**: explicit `cycle_id` if owned/global; otherwise their single owned active cycle.
- **Member**: the active cycle owned by their manager; fallback to an active global (admin-owned) cycle; never another department's cycle.

## 3) Implementation phases

### Phase A — Data & DB foundation

A1. Migration `c6d7e8f9a0b1_per_manager_active_cycles`:
    - Backfill: `UPDATE cycle SET owner_manager_id = <admin_id> WHERE owner_manager_id IS NULL`
      (admin id resolved at migration runtime from the oldest active admin user;
      abort loudly if none exists).
    - Drop `ux_cycle_single_active`.
    - Create `ux_cycle_owner_active`: `UNIQUE (owner_manager_id) WHERE is_active`
      (partial, both dialects). Pre-dedupe: for each owner with multiple actives,
      keep the newest, deactivate the rest.
    - Replace `fn_activate_cycle(p_cycle_id)` body: deactivate only cycles whose
      `owner_manager_id` equals the target's owner (admin-owned target → deactivate
      other admin-owned actives only). Keep SECURITY DEFINER + grants pattern.
A2. `src/models.py`: replace `ux_cycle_single_active` Index definition with the
    per-owner partial unique index (same name change as migration).
A3. Update `z3a4b5c6d7e8` docstring note: superseded by this migration.

### Phase B — Backend scope logic

B1. `backend_app/scope_resolution.py`:
    - `_cycle_owner_match`: unchanged except NULL-owner no longer possible
      (keep defensive branch).
    - `_pick_primary_active_cycle(cycles, scope)`: prefer cycle owned by
      `scope.manager_id` (member) / `scope.actor_id` (manager); fall back to
      admin-owned global; tie-break highest id.
    - `_resolve_effective_cycle_id_for_scope` member branch: resolve to "active
      cycle owned by my manager", else active global; requested id must match,
      else 403 (message updated to name the allowed cycle).
    - Mirror ALL changes in `backend_app/main_runtime_helpers.py` (duplicated copy).
B2. `backend_app/read_query_helpers.py` `cycles.all` / `cycles.active` handlers:
    member collapse uses the new primary-selection rule (manager-owned first,
    then global).
B3. `src/crud_cycle_helpers.py`:
    - Bulk-deactivate becomes per-owner: `WHERE is_active AND owner_manager_id =
      <target.owner_manager_id> AND id <> target`.
    - `_is_last_active_cycle` guard becomes per-owner ("last active cycle in your
      scope").
    - Manager create path already forces ownership — keep.
B4. `src/services/supabase_api_mode_operations.py`:
    - Legacy two-call fallback deactivation filter adds
      `owner_manager_id=eq.<target owner>` (requires reading target row first).
    - Last-active guard query adds same-owner condition.
    - RPC call unchanged (RPC itself now per-owner).

### Phase C — Frontend

C1. `useDeepLinkCycleBootstrap.ts`: `authoritativeActive` selection prefers
    manager-owned over global when both exist (managers/admins); members receive
    the collapsed list from the backend so behavior is automatic.
C2. `AtlasShell.tsx` inactive-cycle banner copy: "not the current active period
    for its owner" wording.
C3. `useAdminActions.ts`:
    - Last-active guard message: "the only active cycle in your scope".
    - Relax `isAdmin` gate on cycle handlers to `canManageCycles`
      (admin OR manager) for activate/deactivate/update-owner/delete-own.
C4. Expose Cycles panel to managers:
    - `useShellAccessControl.ts`: allow `mode === "admin"` for managers but force
      `adminTab === "cycles"` and hide other tabs; rename visible heading to
      "Cycle Management" for managers.
    - `AdminModePanel.tsx`: render tab buttons only for admins; managers get the
      cycles tab directly. Hide Users/Teams/Security/Backup/Audit/AI tabs.
    - `loadAdminResources` fires for managers too (cycles-only loads);
      `teams.all` fetch skipped for managers (D4).
C5. Sidebar: show "Cycles" entry for managers (routes to admin mode, cycles tab).

### Phase D — Tests

D1. Rewrite `tests/test_cycle_single_active.py` + `test_cycle_db_invariant.py`:
    - Two managers may each have one active cycle simultaneously.
    - Same-manager second activation rejected by DB index.
    - Member resolves to manager's active cycle, never another department's.
    - Global (admin-owned) cycle visible to all scopes.
    - Last-active-per-scope guard.
D2. New `tests/test_cycle_scope_resolution.py`: member/manager resolution matrix
    across multiple owners and global cycles.
D3. Frontend: bootstrap auto-select prefers manager-owned; banner renders for
    inactive; panel hidden/shown correctly per role.

### Phase E — Docs & rollout

E1. Update ARCHITECTURE.md (cycle model section), CONFIG_REFERENCE (no new keys),
    README read-kind descriptions if semantics change.
E2. Deploy order: backend-api → worker → spa-web/spa-bff (migrations run on API start).
E3. Verification drill: create two managers with members, activate distinct
  cycles, confirm each member sees only their department's data. **Completed
  2026-08-26.** Manager AI analysis was also verified to retain the selected
  manager-owned cycle context rather than the admin global cycle.

## 4) Risk register

| Risk | Mitigation |
|---|---|
| Unique index creation fails on existing duplicate-active data | Pre-dedupe step in migration (same pattern as z3a4b5c6d7e8) |
| Admin id unresolvable during backfill | Abort migration with explicit error; require manual assignment |
| Member of manager without any cycle | Falls back to global active cycle; if none, existing "No cycle found" error |
| Runtime duplicate logic drift (main_runtime_helpers vs scope_resolution) | Both changed in same commit; add parity test |
| Old clients caching stale dropdown | sessionCycles refresh already wired post-mutation |

## 5) Effort estimate

- Phase A: 1–2 sessions (migration care needed)
- Phase B: 1–2 sessions
- Phase C: 1–2 sessions
- Phase D: 1 session
- Phase E: 0.5 session
Total: ~5–8 focused sessions.
