from __future__ import annotations

import functools
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlmodel import Session

from src.crud import (
    create_cycle,
    get_all_cycles,
    get_active_weekly_plan,
    get_user_by_id,
)
from src.database import get_session_context
from src.serialization_helpers import (
    serialize_cycle_snapshot,
    serialize_user_snapshot,
    serialize_weekly_plan_snapshot,
)

_LOGGER = logging.getLogger(__name__)


class _CachedCallable:
    """Simple memoized callable with a public .clear() method."""

    def __init__(self, fn: Callable) -> None:
        functools.update_wrapper(self, fn)
        self._fn = fn
        self._cache: dict[str, Any] = {}

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        key = json.dumps(
            {"a": args, "k": kwargs},
            default=str,
            sort_keys=True,
        )
        if key not in self._cache:
            self._cache[key] = self._fn(*args, **kwargs)
        return self._cache[key]

    def clear(self) -> None:
        self._cache.clear()


def _serialize_cycle(cycle: Any) -> dict[str, Any] | None:
    return serialize_cycle_snapshot(cycle)


def _serialize_user(user: Any) -> dict[str, Any] | None:
    return serialize_user_snapshot(user)


def _serialize_weekly_plan(plan: Any) -> dict[str, Any] | None:
    return serialize_weekly_plan_snapshot(plan)


def _fetch_all_cycles_raw() -> list[dict[str, Any]]:
    cycles = get_all_cycles()
    return [cycle for cycle in (_serialize_cycle(c) for c in (cycles or [])) if cycle is not None]


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

    _cached_get_all_cycles.clear()
    return [_serialize_cycle(created)], None


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
