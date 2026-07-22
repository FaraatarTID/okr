from __future__ import annotations

from typing import Any, Callable

from src.models import UserRole


def _enum_value(value: Any) -> Any:
    """Extract .value from an enum if present, otherwise return as-is."""
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def serialize_cycle_snapshot(cycle: Any) -> dict[str, Any] | None:
    if not cycle:
        return None
    cycle_id = getattr(cycle, "id", None)
    if cycle_id is None:
        return None
    return {
        "id": int(cycle_id),
        "title": str(getattr(cycle, "title", "") or ""),
        "start_date": getattr(cycle, "start_date", None),
        "end_date": getattr(cycle, "end_date", None),
        "is_active": bool(getattr(cycle, "is_active", True)),
        "owner_manager_id": getattr(cycle, "owner_manager_id", None),
    }


def _normalize_role_value(raw_role: Any, *, default_role: Any = UserRole.MEMBER) -> str:
    value = raw_role if raw_role is not None else default_role
    if hasattr(value, "value"):
        value = getattr(value, "value")
    return str(value or "member").lower()


def serialize_user_snapshot(
    user: Any,
    *,
    role_value_fn: Callable[[Any], Any] | None = None,
) -> dict[str, Any] | None:
    if not user:
        return None
    user_id = getattr(user, "id", None)
    if user_id is None:
        return None
    raw_role = getattr(user, "role", UserRole.MEMBER)
    role_value = role_value_fn(raw_role) if role_value_fn is not None else raw_role
    return {
        "id": int(user_id),
        "username": str(getattr(user, "username", "") or ""),
        "display_name": getattr(user, "display_name", None),
        "role": _normalize_role_value(role_value),
        "manager_id": getattr(user, "manager_id", None),
        "team_id": getattr(user, "team_id", None),
        "is_active": bool(getattr(user, "is_active", True)),
        "must_change_password": bool(getattr(user, "must_change_password", False)),
    }


def serialize_weekly_plan_snapshot(plan: Any) -> dict[str, Any] | None:
    if not plan:
        return None
    plan_id = getattr(plan, "id", None)
    if plan_id is None:
        return None
    return {
        "id": int(plan_id),
        "user_id": getattr(plan, "user_id", None),
        "week_start_date": getattr(plan, "week_start_date", None),
        "week_end_date": getattr(plan, "week_end_date", None),
        "priority_1": str(getattr(plan, "priority_1", "") or ""),
        "priority_2": getattr(plan, "priority_2", None),
        "priority_3": getattr(plan, "priority_3", None),
        "created_at": getattr(plan, "created_at", None),
        "is_active": bool(getattr(plan, "is_active", True)),
    }
