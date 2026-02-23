"""Filter and data-preparation helpers for leadership dashboard."""

from __future__ import annotations

from typing import Any, Callable


def render_refresh_controls(*, st_module: Any) -> None:
    """Render refresh button and clear relevant dashboard caches."""
    col_refresh, _col_spacer = st_module.columns([1, 5])
    with col_refresh:
        if st_module.button(
            "🔄 Refresh Data", help="Reload dashboard data", key="dash_refresh"
        ):
            keys_to_clear = [
                key
                for key in st_module.session_state.keys()
                if str(key).startswith("okr_data_cache_")
            ]
            for key in keys_to_clear:
                del st_module.session_state[key]

            if "report_summary" in st_module.session_state:
                del st_module.session_state["report_summary"]
            st_module.rerun()


def resolve_selected_members(
    *,
    st_module: Any,
    username: str,
    user_role: str,
    cached_get_all_users_fn: Callable[[], list[Any]],
    cached_get_team_members_fn: Callable[[Any], list[Any]],
    get_user_by_id_fn: Callable[[Any], Any],
) -> tuple[list[str], dict[str, str], bool]:
    """Resolve dashboard member filter state.

    Returns (selected_members, member_display_map, should_abort).
    """
    selected_members = [username]
    member_display_map = {
        username: str(st_module.session_state.get("display_name", username))
    }

    if user_role not in ["admin", "manager"]:
        return selected_members, member_display_map, False

    st_module.markdown("#### 👥 Team Filter")

    if user_role == "admin":
        all_users = list(cached_get_all_users_fn() or [])
    else:
        manager_id = st_module.session_state.get("user_id")
        all_users = list(cached_get_team_members_fn(manager_id) or [])
        manager_user = get_user_by_id_fn(manager_id)
        if manager_user and manager_user not in all_users:
            all_users.insert(0, manager_user)

    active_users = [user for user in all_users if getattr(user, "is_active", False)]
    member_display_map = {
        str(user.username): str(getattr(user, "display_name", None) or user.username)
        for user in active_users
    }
    member_usernames = [str(user.username) for user in active_users]

    if member_usernames:
        selected_usernames = st_module.multiselect(
            "Select members to include in dashboard",
            options=member_usernames,
            default=member_usernames,
            format_func=lambda uname: member_display_map.get(uname, uname),
            help="Filter dashboard metrics to show data for selected members only",
            key="dash_members",
        )
        selected_members = list(selected_usernames)

        if not selected_members:
            st_module.warning("Please select at least one team member.")
            return selected_members, member_display_map, True

    st_module.markdown("---")
    return selected_members, member_display_map, False


def build_overdue_tasks(
    *,
    cycle_id: Any,
    cached_get_all_tasks_by_cycle_fn: Callable[..., list[Any]],
    cycle_task_scan_limit_fn: Callable[[], int],
    utc_now_naive_fn: Callable[[], Any],
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    users_map: dict[Any, Any],
    logger: Any,
) -> tuple[list[dict[str, Any]], int, int]:
    """Collect overdue tasks for the cycle and enrich with owner display."""
    overdue_tasks: list[dict[str, Any]] = []
    task_scan_limit = int(cycle_task_scan_limit_fn() or 0)
    tasks = []
    try:
        tasks = list(
            cached_get_all_tasks_by_cycle_fn(cycle_id, limit=task_scan_limit) or []
        )
        for task in tasks:
            deadline_ms = None
            task_deadline = getattr(task, "deadline", None)
            if task_deadline:
                if hasattr(task_deadline, "timestamp"):
                    deadline_ms = int(task_deadline.timestamp() * 1000)
                else:
                    deadline_ms = task_deadline

            node = {
                "type": "TASK",
                "deadline": deadline_ms,
                "progress": getattr(task, "progress", 0),
                "createdAt": int(
                    getattr(task, "created_at", utc_now_naive_fn()).timestamp() * 1000
                ),
                "title": getattr(task, "title", "Untitled"),
            }
            status_code, _, _ = get_deadline_status_fn(node)
            if status_code != "overdue":
                continue

            owner_display = "Unknown"
            try:
                if (
                    task.key_result
                    and task.key_result.objective
                    and task.key_result.objective.goal
                ):
                    goal_owner_id = task.key_result.objective.goal.owner_id
                    if goal_owner_id and goal_owner_id in users_map:
                        user_obj = users_map[goal_owner_id]
                        owner_display = (
                            getattr(user_obj, "display_name", None)
                            or getattr(user_obj, "username", None)
                            or "Unknown"
                        )
            except Exception as exc:
                logger.debug("Failed to resolve overdue task owner display: %s", exc)
                owner_display = "Unknown"

            overdue_tasks.append(
                {
                    "title": str(node.get("title", "Untitled")),
                    "owner": str(owner_display),
                    "progress": int(node.get("progress", 0) or 0),
                }
            )
    except Exception as exc:
        logger.warning("Failed while building overdue task list: %s", exc)
        overdue_tasks = []

    return overdue_tasks, len(tasks), task_scan_limit
