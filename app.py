from __future__ import annotations

import functools
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from src.services.app_shell_runtime import (
    KeyedSnapshotCache,
    SnapshotCache,
    bootstrap_default_cycle_for_facade,
    build_cycle_selector_mapping,
    serialize_cycle,
    serialize_user,
    serialize_weekly_plan,
    weekly_plan_cache_bucket,
)

from src.crud import (
    create_cycle,
    get_all_cycles,
    get_active_weekly_plan,
    get_user_by_id,
)
from src.serialization_helpers import (
    serialize_cycle_snapshot,
    serialize_user_snapshot,
    serialize_weekly_plan_snapshot,
)

_LOGGER = logging.getLogger(__name__)


class _CachedCallable:
    """Memoized callable with TTL, distributed-invalidation awareness, and a
    public .clear() method.

    Entries older than ``ttl_seconds`` are refetched. Additionally, each call
    consults the distributed cache-invalidation signal so a mutation on another
    node (or process) drops stale entries promptly.
    """

    def __init__(
        self,
        fn: Callable,
        *,
        ttl_seconds: float = 5.0,
        distributed_invalidation: bool = True,
    ) -> None:
        functools.update_wrapper(self, fn)
        self._fn = fn
        self._ttl_seconds = ttl_seconds
        self._distributed_invalidation = distributed_invalidation
        self._cache: dict[str, tuple[float, Any]] = {}
        self._last_seen_invalidation_ts = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        key = json.dumps(
            {"a": args, "k": kwargs},
            default=str,
            sort_keys=True,
        )
        now = time.monotonic()
        if self._distributed_invalidation:
            try:
                from src.utils.cache_utils import check_distributed_cache_staleness

                check_distributed_cache_staleness()
            except Exception:
                pass
        entry = self._cache.get(key)
        if entry is not None:
            cached_at, value = entry
            expired = (now - cached_at) >= self._ttl_seconds
            invalidated = (
                self._distributed_invalidation
                and _last_invalidation_ts() > 0
                and _last_invalidation_ts() != self._last_seen_invalidation_ts
            )
            if not expired and not invalidated:
                return value
        value = self._fn(*args, **kwargs)
        self._cache[key] = (now, value)
        return value

    def clear(self) -> None:
        self._cache.clear()
        # Record that we've consumed the current invalidation signal.
        try:
            from src.services.distributed_state_service import (
                get_last_invalidation_timestamp,
            )

            ts = get_last_invalidation_timestamp()
            if ts:
                self._last_seen_invalidation_ts = ts
        except Exception:
            pass


def _last_invalidation_ts() -> int:
    try:
        from src.services.distributed_state_service import (
            get_last_invalidation_timestamp,
        )

        return get_last_invalidation_timestamp()
    except Exception:
        return 0


def _make_distributed_stale_check() -> Callable[[], bool]:
    seen_invalidation_ts = 0

    def is_stale() -> bool:
        nonlocal seen_invalidation_ts
        try:
            from src.utils.cache_utils import check_distributed_cache_staleness

            check_distributed_cache_staleness()
        except Exception:
            pass
        current_ts = _last_invalidation_ts()
        if current_ts and current_ts != seen_invalidation_ts:
            seen_invalidation_ts = current_ts
            return True
        return False

    return is_stale


def _fetch_all_cycles_raw() -> list[dict[str, Any]]:
    cycles = get_all_cycles()
    return [
        cycle
        for cycle in (_serialize_cycle(c) for c in (cycles or []))
        if cycle is not None
    ]


_cached_get_all_cycles = SnapshotCache(
    _fetch_all_cycles_raw,
    ttl_seconds=5.0,
    stale_check=_make_distributed_stale_check(),
)


def _get_weekly_plan_snapshot(user_id: int) -> Optional[dict[str, Any]]:
    plan = get_active_weekly_plan(user_id)
    if plan is None:
        return None
    return serialize_weekly_plan_snapshot(plan)


def _get_user_snapshot(user_id: int) -> Optional[dict[str, Any]]:
    user = get_user_by_id(user_id)
    if user is None:
        return None
    return serialize_user_snapshot(user)


_cached_get_active_weekly_plan_snapshot = KeyedSnapshotCache(
    _get_weekly_plan_snapshot,
    ttl_seconds=5.0,
    stale_check=_make_distributed_stale_check(),
)
_cached_get_user_runtime_snapshot = KeyedSnapshotCache(
    _get_user_snapshot,
    ttl_seconds=5.0,
    stale_check=_make_distributed_stale_check(),
)


def _resolve_app_shell_runtime(user_id: int) -> dict[str, Any]:
    user = _cached_get_user_runtime_snapshot(user_id)
    weekly_plan = _cached_get_active_weekly_plan_snapshot(user_id)

    show_admin_default_password_warning = False
    if user and bool(user.get("must_change_password")):
        show_admin_default_password_warning = True

    return {
        "user": user,
        "weekly_plan": weekly_plan,
        "show_admin_default_password_warning": show_admin_default_password_warning,
    }


# Compatibility names remain available while callers migrate to the canonical
# service boundary.
_serialize_cycle = serialize_cycle
_serialize_user = serialize_user
_serialize_weekly_plan = serialize_weekly_plan
_weekly_plan_cache_bucket = weekly_plan_cache_bucket
_build_cycle_selector_payload = build_cycle_selector_mapping


def _bootstrap_default_cycle_if_needed(
    cycles: list[dict[str, Any]],
    *,
    username: str,
    user_role: str,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    return bootstrap_default_cycle_for_facade(
        cycles,
        username=username,
        user_role=user_role,
        create_cycle=create_cycle,
        clear_cache=_cached_get_all_cycles.clear,
    )
