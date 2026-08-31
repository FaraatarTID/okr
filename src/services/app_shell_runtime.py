"""Canonical service boundary for app-shell runtime snapshots."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Generic, Hashable, Iterable, Mapping, Sequence, TypeVar

from src.serialization_helpers import (
    serialize_cycle_snapshot,
    serialize_user_snapshot,
    serialize_weekly_plan_snapshot,
)

T = TypeVar("T")
_UNSET = object()


class SnapshotCache(Generic[T]):
    """Small explicit-clear cache for immutable runtime snapshots."""

    def __init__(
        self,
        loader: Callable[[], T],
        *,
        ttl_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        stale_check: Callable[[], bool] | None = None,
    ) -> None:
        self._loader = loader
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._stale_check = stale_check
        self._value: object = _UNSET
        self._cached_at = 0.0

    def __call__(self) -> T:
        if self._stale_check is not None and self._stale_check():
            self.clear()
        now = self._clock()
        expired = (
            self._ttl_seconds is not None
            and self._value is not _UNSET
            and (now - self._cached_at) >= self._ttl_seconds
        )
        if self._value is _UNSET or expired:
            self._value = self._loader()
            self._cached_at = now
        return self._value  # type: ignore[return-value]

    def clear(self) -> None:
        self._value = _UNSET


class KeyedSnapshotCache(Generic[T]):
    """Lazily cache one immutable snapshot per hashable runtime key."""

    def __init__(
        self,
        loader: Callable[[Hashable], T],
        *,
        ttl_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
        stale_check: Callable[[], bool] | None = None,
    ) -> None:
        self._loader = loader
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._stale_check = stale_check
        self._values: dict[Hashable, tuple[float, T]] = {}

    def __call__(self, key: Hashable) -> T:
        if self._stale_check is not None and self._stale_check():
            self.clear()
        now = self._clock()
        entry = self._values.get(key)
        if entry is not None:
            cached_at, value = entry
            if self._ttl_seconds is None or (now - cached_at) < self._ttl_seconds:
                return value
        value = self._loader(key)
        self._values[key] = (now, value)
        return value

    def invalidate(self, key: Hashable) -> None:
        self._values.pop(key, None)

    def clear(self) -> None:
        self._values.clear()


class SnapshotCacheRegistry:
    """Coordinate invalidation for related runtime snapshot caches."""

    def __init__(self, caches: Iterable[SnapshotCache[Any]] = ()) -> None:
        self._caches = tuple(caches)

    def clear(self) -> None:
        for cache in self._caches:
            cache.clear()


def serialize_cycle(cycle: Any) -> dict[str, Any] | None:
    """Serialize a cycle through the canonical snapshot contract."""
    return serialize_cycle_snapshot(cycle)


def serialize_user(user: Any) -> dict[str, Any] | None:
    """Serialize a user through the canonical snapshot contract."""
    return serialize_user_snapshot(user)


def serialize_weekly_plan(plan: Any) -> dict[str, Any] | None:
    """Serialize a weekly plan through the canonical snapshot contract."""
    return serialize_weekly_plan_snapshot(plan)


def weekly_plan_cache_bucket(dt: datetime) -> str:
    """Return the ISO date for the Monday containing ``dt``."""
    monday = dt - timedelta(days=dt.weekday())
    return monday.date().isoformat()


def build_cycle_selector_payload(
    cycles: Sequence[Mapping[str, Any]],
) -> tuple[list[int], list[str]]:
    """Build stable ID and label lists from cycle snapshots."""
    ordered = sorted(cycles, key=lambda cycle: int(cycle["id"]))
    return (
        [int(cycle["id"]) for cycle in ordered],
        [str(cycle.get("title", "") or "") for cycle in ordered],
    )


def build_cycle_selector_mapping(
    cycles: Sequence[Mapping[str, Any]],
) -> tuple[list[int], dict[int, str]]:
    """Build the legacy-compatible selector mapping without reordering cycles."""
    cycle_ids: list[int] = []
    labels: dict[int, str] = {}
    for cycle in cycles:
        cycle_id = int(cycle.get("id", 0))
        cycle_ids.append(cycle_id)
        title = str(cycle.get("title", "") or "")
        labels[cycle_id] = f"{title} #{cycle_id}"
    return cycle_ids, labels


def create_cycle_snapshot_cache(
    loader: Callable[[], Sequence[Any]],
) -> SnapshotCache[list[dict[str, Any]]]:
    """Create a cache that materializes cycle models into plain snapshots."""

    def load_snapshots() -> list[dict[str, Any]]:
        return [
            snapshot
            for cycle in loader()
            if (snapshot := serialize_cycle(cycle)) is not None
        ]

    return SnapshotCache(load_snapshots)


def create_user_snapshot_cache(
    loader: Callable[[], Any],
) -> SnapshotCache[dict[str, Any] | None]:
    """Create a cache that materializes one user into a plain snapshot."""
    return SnapshotCache(lambda: serialize_user(loader()))


def create_weekly_plan_snapshot_cache(
    loader: Callable[[], Any],
) -> SnapshotCache[dict[str, Any] | None]:
    """Create a cache that materializes one weekly plan snapshot."""
    return SnapshotCache(lambda: serialize_weekly_plan(loader()))


def bootstrap_default_cycle_if_needed(
    cycles: Sequence[Mapping[str, Any]],
    *,
    is_admin: bool,
    create_cycle: Callable[[], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Create a default cycle only for an authorized admin caller."""
    current = [dict(cycle) for cycle in cycles]
    if current or not is_admin:
        return current, None
    try:
        current.append(dict(create_cycle()))
    except PermissionError as exc:
        return current, str(exc)
    return current, None


def bootstrap_default_cycle_for_facade(
    cycles: list[dict[str, Any]],
    *,
    username: str,
    user_role: str,
    create_cycle: Callable[..., Any],
    clear_cache: Callable[[], None],
) -> tuple[list[dict[str, Any]], str | None]:
    """Preserve the root facade's default-cycle bootstrap contract."""
    if cycles:
        return cycles, None

    if str(user_role or "").strip().lower() != "admin":
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

    snapshot = serialize_cycle(created)
    if snapshot is None:
        return [], "Unable to build default cycle payload."

    clear_cache()
    return [snapshot], None


def create_runtime_snapshot_caches(
    *,
    load_cycles: Callable[[], Sequence[Any]],
    load_user: Callable[[], Any],
    load_weekly_plan: Callable[[], Any],
) -> dict[str, Any]:
    """Create the app-shell caches and their shared invalidation registry."""
    caches = {
        "cycles": create_cycle_snapshot_cache(load_cycles),
        "user": create_user_snapshot_cache(load_user),
        "weekly_plan": create_weekly_plan_snapshot_cache(load_weekly_plan),
    }
    caches["registry"] = SnapshotCacheRegistry(caches.values())
    return caches


def create_keyed_runtime_snapshot_caches(
    *,
    load_cycles: Callable[[], Sequence[Any]],
    load_user: Callable[[Hashable], Any],
    load_weekly_plan: Callable[[Hashable], Any],
) -> dict[str, Any]:
    """Create runtime caches with user-scoped snapshots keyed by identity."""
    caches = {
        "cycles": create_cycle_snapshot_cache(load_cycles),
        "user": KeyedSnapshotCache(
            lambda user_id: serialize_user_snapshot(load_user(user_id))
        ),
        "weekly_plan": KeyedSnapshotCache(
            lambda user_id: serialize_weekly_plan_snapshot(load_weekly_plan(user_id))
        ),
    }
    caches["registry"] = SnapshotCacheRegistry(caches.values())
    return caches
