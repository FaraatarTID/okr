"""Inspector form helper routines."""

from __future__ import annotations

from typing import Any, Callable


def resolve_task_assignee(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    node: Any,
    node_type_upper: str,
    node_id: int,
    get_all_users_fn: Callable[[], list[Any]],
    get_user_by_id_fn: Callable[[Any], Any],
    get_team_members_fn: Callable[[Any], list[Any]],
) -> Any:
    current_assignee_id = (
        getattr(node, "assignee_id", None) if node_type_upper == "TASK" else None
    )
    if node_type_upper != "TASK":
        return current_assignee_id

    user_role = session_state.get("user_role")
    if user_role in ["admin", "manager"]:
        potential_assignees: list[Any] = []
        if user_role == "admin":
            potential_assignees = list(get_all_users_fn() or [])
        elif user_role == "manager":
            manager_id = session_state.get("user_id")
            manager_obj = get_user_by_id_fn(manager_id)
            potential_assignees = list(get_team_members_fn(manager_id) or [])
            if manager_obj:
                potential_assignees.append(manager_obj)

        assignee_ids: list[int] = []
        assignee_labels: dict[int, str] = {}
        for user_option in potential_assignees:
            user_id = getattr(user_option, "id", None)
            if user_id is None:
                continue
            user_id = int(user_id)
            assignee_ids.append(user_id)
            display_name = (
                getattr(user_option, "display_name", None)
                or getattr(user_option, "username", None)
                or f"user_{user_id}"
            )
            username = getattr(user_option, "username", None) or f"user_{user_id}"
            assignee_labels[user_id] = f"{display_name} (@{username}) | #{user_id}"

        if assignee_ids:
            curr_idx_ass = 0
            if current_assignee_id:
                try:
                    curr_idx_ass = assignee_ids.index(int(current_assignee_id))
                except ValueError:
                    curr_idx_ass = 0

            selected_assignee_id = st_module.selectbox(
                "Assign To",
                options=assignee_ids,
                index=curr_idx_ass,
                format_func=lambda uid: assignee_labels.get(uid, f"User #{uid}"),
                key=f"assign_sel_{node_id}",
            )
            return int(selected_assignee_id)
        return current_assignee_id

    assignee_obj = getattr(node, "assignee", None)
    if assignee_obj:
        display_name = (
            getattr(assignee_obj, "display_name", None)
            or getattr(assignee_obj, "username", None)
            or "Unknown"
        )
        st_module.info(f"👥 **Assigned To:** {display_name}")
    else:
        st_module.info("👥 **Unassigned**")
    return current_assignee_id
