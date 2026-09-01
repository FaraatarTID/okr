# Legacy Facade Symbol Migration Map

Documentation HQ: [README](../README.md)

Status: `DESIGN HANDOFF` for P0-01 and P0-04.

This map translates the actively tested root `app.py` symbols into a proposed canonical service interface. It is a design handoff, not an implementation claim.

## Symbol map

| Current symbol | Current behavior under test | Proposed canonical owner | Compatibility rule |
|---|---|---|---|
| `_cached_get_all_cycles` | Cached plain cycle snapshots | `src.services.app_shell_runtime` | Preserve snapshot shape and explicit cache clearing |
| `_build_cycle_selector_payload` | Stable ID-based cycle selector payload | `src.services.app_shell_runtime` | Preserve IDs and stable labels |
| `_bootstrap_default_cycle_if_needed` | Permission-aware default-cycle bootstrap | `src.services.app_shell_runtime` | Non-admin calls must not create; permission errors remain explicit |
| `_weekly_plan_cache_bucket` | Stable week bucket calculation | `src.services.app_shell_runtime` | Preserve Monday bucket semantics |
| `_cached_get_active_weekly_plan_snapshot` | Cached active weekly-plan snapshot | `src.services.app_shell_runtime` | Preserve cache hit behavior and snapshot isolation |
| `_cached_get_user_runtime_snapshot` | Cached user runtime snapshot | `src.services.app_shell_runtime` | Preserve cache invalidation semantics |
| `_resolve_app_shell_runtime` | Aggregates shell runtime data | `src.services.app_shell_runtime` | Preserve returned fields and cache behavior |
| `_serialize_cycle` | Safe cycle serialization | `src.services.serialization` or explicit adapter | `None` remains `None`; output remains JSON-safe |
| `_serialize_user` | Safe user serialization | `src.services.serialization` or explicit adapter | `None` remains `None`; output remains JSON-safe |
| `_serialize_weekly_plan` | Safe weekly-plan serialization | `src.services.serialization` or explicit adapter | `None` remains `None`; output remains JSON-safe |

The snapshot and bootstrap implementation layer is now available in `src.services.app_shell_runtime`: snapshot serializers delegate to the established contract, `weekly_plan_cache_bucket` preserves Monday-based cache buckets, `build_cycle_selector_payload` produces ID-sorted selectors with stable titles, `SnapshotCache` and `KeyedSnapshotCache` provide explicit-clear snapshot caching plus precise per-key invalidation, injected factories materialize isolated cycle, user, and weekly-plan snapshots, `SnapshotCacheRegistry` coordinates invalidation, `bootstrap_default_cycle_if_needed` enforces the non-admin no-create rule with explicit admin and permission-error behavior, and the runtime factories compose shared invalidation for both unkeyed and user-keyed snapshots. Their contract is covered by 21 focused tests in [test_facade_service_boundary.py](../tests/test_facade_service_boundary.py).

The production facade now delegates cycle runtime caching to `SnapshotCache` and user/weekly-plan runtime caching to `KeyedSnapshotCache`, preserving the legacy five-second TTL, explicit `.clear()` hooks, and distributed-staleness checks. Superseded serializer, selector, bucket, and bootstrap implementations have been removed from `app.py`; it remains a compatibility layer for callers and selector return shapes.

The proposed module names are intentionally subject to P0-01 package review. The important boundary is that the behavior moves behind a canonical service interface, while `app.py` becomes a thin compatibility facade during migration.

## Migration sequence

1. Introduce the canonical service functions without changing behavior.
2. Add contract tests against the canonical interface using the existing 8 behavior cases.
3. Change `app.py` to delegate to the canonical interface while retaining compatibility names temporarily.

The compatibility delegation is now implemented for `_serialize_cycle`, `_serialize_user`, `_serialize_weekly_plan`, `_weekly_plan_cache_bucket`, and `_build_cycle_selector_payload`. The selector delegates to the legacy-compatible canonical mapping and preserves input order plus `Title #ID` labels. `_bootstrap_default_cycle_if_needed` now uses a thin facade wrapper around `bootstrap_default_cycle_for_facade`, supplying the legacy creator and cache-clear dependencies while preserving its public signature. The platform login route and backend response-scope serializer implementations now call the canonical serializers directly; `read_query_helpers.py` now uses canonical cycle and weekly-plan serializers directly and resolves user serialization through one canonical fallback with an explicit injectable override for parity-sensitive callers.
4. Migrate callers and tests to the canonical interface.
5. Add a deprecation marker for direct facade imports.
6. Remove compatibility names only after caller and operator evidence supports removal.

## Non-negotiable behavior

- Cache values remain plain snapshots rather than live ORM objects.
- Cache invalidation remains explicit after cycle or user mutations.
- Permission errors during bootstrap remain distinguishable from empty data.
- Weekly cache buckets remain stable across days in the same week.
- Serializers remain safe for missing objects.
- The canonical service interface must not import `backend_app`.

## Acceptance evidence

- Canonical service contract tests pass.
- Existing facade tests pass unchanged during the delegation phase.
- Import-boundary check passes.
- Caller inventory shows no new direct facade imports.
- The status ledger links the implementation and verification evidence.
