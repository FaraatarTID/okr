from __future__ import annotations

import functools
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional


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


def _serialize_cycle(cycle: Any) -> dict[str, Any] | None:
    return serialize_cycle_snapshot(cycle)


def _serialize_user(user: Any) -> dict[str, Any] | None:
    return serialize_user_snapshot(user)


def _serialize_weekly_plan(plan: Any) -> dict[str, Any] | None:
    return serialize_weekly_plan_snapshot(plan)


def _fetch_all_cycles_raw() -> list[dict[str, Any]]:
    cycles = get_all_cycles()
    return [
        cycle
        for cycle in (_serialize_cycle(c) for c in (cycles or []))
        if cycle is not None
    ]


_cached_get_all_cycles = _CachedCallable(_fetch_all_cycles_raw)


def _build_cycle_selector_payload(
    cycles: list[dict[str, Any]],
) -> tuple[list[int], dict[int, str]]:
    cycle_ids: list[int] = []
    labels: dict[int, str] = {}
    for cycle in cycles:
        cid = int(cycle.get("id", 0))
        title = str(cycle.get("title", "") or "")
        cycle_ids.append(cid)
        labels[cid] = f"{title} #{cid}"
    return cycle_ids, labels


def _bootstrap_default_cycle_if_needed(
    cycles: list[dict[str, Any]],
    *,
    username: str,
    user_role: str,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    if cycles:
        return cycles, None

    role = str(user_role or "").strip().lower()
    if role != "admin":
        return [], "No cycles found. Ask an admin to create the first cycle."

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        created = create_cycle(
            title="Default Cycle",
            start_date=now - timedelta(days=7),
            end_date=now + timedelta(days=83),
            is_active=True,
            actor_username=username,
        )
    except PermissionError:
        return [], "No cycles found. Ask an admin to create the first cycle."

    serialized_created = _serialize_cycle(created)
    if serialized_created is None:
        return [], "Unable to build default cycle payload."

    _cached_get_all_cycles.clear()
    return [serialized_created], None


def _weekly_plan_cache_bucket(dt: datetime) -> str:
    if dt.weekday() == 0:
        return dt.strftime("%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def _get_weekly_plan_snapshot(user_id: int) -> Optional[dict[str, Any]]:
    plan = get_active_weekly_plan(user_id)
    if plan is None:
        return None
    return _serialize_weekly_plan(plan)


def _get_user_snapshot(user_id: int) -> Optional[dict[str, Any]]:
    user = get_user_by_id(user_id)
    if user is None:
        return None
    return _serialize_user(user)


_cached_get_active_weekly_plan_snapshot = _CachedCallable(_get_weekly_plan_snapshot)
_cached_get_user_runtime_snapshot = _CachedCallable(_get_user_snapshot)


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
