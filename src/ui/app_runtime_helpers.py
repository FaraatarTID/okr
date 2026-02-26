"""Runtime and cycle snapshot helpers extracted from app.py."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable


def cycle_to_snapshot(cycle) -> dict | None:
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
        "is_active": bool(getattr(cycle, "is_active", False)),
    }


def date_label(value) -> str:
    if value is None:
        return ""
    try:
        return value.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def format_cycle_label(
    cycle_snapshot: dict, *, date_label_fn: Callable[[Any], str]
) -> str:
    cycle_id = int(cycle_snapshot.get("id"))
    title = str(cycle_snapshot.get("title", "") or "").strip() or "Untitled cycle"
    start_label = date_label_fn(cycle_snapshot.get("start_date"))
    end_label = date_label_fn(cycle_snapshot.get("end_date"))
    if start_label and end_label:
        return f"{title} ({start_label} -> {end_label}) | #{cycle_id}"
    if start_label:
        return f"{title} (from {start_label}) | #{cycle_id}"
    if end_label:
        return f"{title} (until {end_label}) | #{cycle_id}"
    return f"{title} | #{cycle_id}"


def build_cycle_selector_payload(
    cycles: list[dict],
    *,
    format_cycle_label_fn: Callable[[dict], str],
) -> tuple[list[int], dict[int, str]]:
    cycle_ids: list[int] = []
    labels: dict[int, str] = {}
    for cycle in cycles:
        cycle_id = cycle.get("id")
        if cycle_id is None:
            continue
        cycle_id_int = int(cycle_id)
        cycle_ids.append(cycle_id_int)
        labels[cycle_id_int] = format_cycle_label_fn(cycle)
    return cycle_ids, labels


def cached_get_all_cycles(
    *,
    get_all_cycles_fn: Callable[[], list[Any]],
    cycle_to_snapshot_fn: Callable[[Any], dict | None],
) -> list[dict]:
    snapshots: list[dict] = []
    for cycle in get_all_cycles_fn():
        payload = cycle_to_snapshot_fn(cycle)
        if payload:
            snapshots.append(payload)
    return snapshots


def bootstrap_default_cycle_if_needed(
    cycles: list[dict],
    *,
    username: str,
    user_role: str,
    admin_role_value: str,
    utc_now_naive_fn: Callable[[], Any],
    create_cycle_fn: Callable[..., Any],
    cycle_to_snapshot_fn: Callable[[Any], dict | None],
    clear_cycles_cache_fn: Callable[[], Any],
    error_log_fn: Callable[[str, Exception], Any],
) -> tuple[list[dict], str | None]:
    if cycles:
        return cycles, None

    if str(user_role).lower() != str(admin_role_value).lower():
        return [], "No cycles are configured yet. Ask an admin to create one."

    now = utc_now_naive_fn()
    quarter = ((now.month - 1) // 3) + 1
    try:
        default_cycle = create_cycle_fn(
            title=f"Q{quarter} {now.year}",
            start_date=now,
            end_date=now + timedelta(days=90),
            is_active=True,
            actor_username=username,
        )
    except PermissionError:
        return [], "No cycles are configured yet. Ask an admin to create one."
    except Exception as exc:
        error_log_fn("Default cycle bootstrap failed", exc)
        return [], "No cycles available and default cycle creation failed."

    default_cycle_snapshot = cycle_to_snapshot_fn(default_cycle)
    if not default_cycle_snapshot:
        return [], "No cycles available and default cycle creation failed."
    clear_cycles_cache_fn()
    return [default_cycle_snapshot], None


def cached_get_user_runtime_snapshot(
    user_id: int,
    *,
    get_user_by_id_fn: Callable[[int], Any],
    build_runtime_user_snapshot_fn: Callable[[Any], dict | None],
):
    user = get_user_by_id_fn(int(user_id))
    return build_runtime_user_snapshot_fn(user)


def weekly_plan_cache_bucket(
    *,
    now=None,
    utc_now_naive_fn: Callable[[], Any] | None = None,
) -> str:
    point = now or (utc_now_naive_fn() if utc_now_naive_fn else None)
    if point is None:
        raise ValueError("weekly_plan_cache_bucket requires now or utc_now_naive_fn")
    week_start = (point - timedelta(days=point.weekday())).date()
    return week_start.isoformat()


def cached_get_active_weekly_plan_snapshot(
    user_id: int,
    week_bucket: str,
    *,
    get_active_weekly_plan_fn: Callable[[int], Any],
):
    _ = week_bucket
    plan = get_active_weekly_plan_fn(int(user_id))
    if not plan:
        return None
    return {
        "priority_1": plan.priority_1,
        "priority_2": plan.priority_2,
        "priority_3": plan.priority_3,
    }


def get_active_weekly_plan_snapshot(
    user_id: int,
    *,
    now=None,
    weekly_plan_cache_bucket_fn: Callable[..., str],
    cached_get_active_weekly_plan_snapshot_fn: Callable[[int, str], Any],
):
    return cached_get_active_weekly_plan_snapshot_fn(
        int(user_id),
        weekly_plan_cache_bucket_fn(now=now),
    )


def should_warn_default_admin_password(
    user_snapshot: dict | None,
    *,
    admin_role_value: str,
) -> bool:
    if not user_snapshot:
        return False
    if str(user_snapshot.get("role") or "").lower() != str(admin_role_value).lower():
        return False
    return bool(user_snapshot.get("must_change_password"))


def build_runtime_user_snapshot(user) -> dict | None:
    if not user:
        return None
    role_attr = getattr(user, "role", None)
    role_value = role_attr.value if hasattr(role_attr, "value") else str(role_attr)
    return {
        "id": int(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": role_value,
        "manager_id": user.manager_id,
        "is_active": bool(user.is_active),
        "must_change_password": bool(user.must_change_password),
    }


def resolve_app_shell_runtime_from_user_snapshot(
    snapshot: dict | None,
    *,
    cached_get_all_cycles_fn: Callable[[], list[dict]],
    get_active_weekly_plan_snapshot_fn: Callable[[int], Any],
    should_warn_default_admin_password_fn: Callable[[dict | None], bool],
) -> dict:
    if not snapshot:
        return {
            "user": None,
            "cycles": [],
            "weekly_plan": None,
            "show_admin_default_password_warning": False,
        }
    user_id = snapshot.get("id")
    if user_id is None:
        return {
            "user": None,
            "cycles": [],
            "weekly_plan": None,
            "show_admin_default_password_warning": False,
        }
    user_id = int(user_id)
    return {
        "user": snapshot,
        "cycles": cached_get_all_cycles_fn(),
        "weekly_plan": get_active_weekly_plan_snapshot_fn(user_id),
        "show_admin_default_password_warning": should_warn_default_admin_password_fn(
            snapshot
        ),
    }


def resolve_app_shell_runtime(
    user_id: int,
    *,
    cached_get_user_runtime_snapshot_fn: Callable[[int], dict | None],
    resolve_app_shell_runtime_from_user_snapshot_fn: Callable[[dict | None], dict],
) -> dict:
    snapshot = cached_get_user_runtime_snapshot_fn(int(user_id))
    return resolve_app_shell_runtime_from_user_snapshot_fn(snapshot)
