"""Inspector helper routines for assignment and lifecycle state sections."""

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
    """Resolve editable/read-only assignee display based on current role."""
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


def resolve_lifecycle_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    lifecycle_state_enum: Any,
    get_allowed_transitions_fn: Callable[[Any], list[Any]],
    state_icons: dict[Any, str],
    state_hints: dict[Any, str],
) -> tuple[Any, str]:
    """Resolve lifecycle transitions and optional closing reflection."""
    current_state = getattr(node, "state", lifecycle_state_enum.DRAFT)
    try:
        current_state = lifecycle_state_enum(current_state)
    except Exception:
        current_state = lifecycle_state_enum.DRAFT

    new_state = current_state
    new_reflection = str(getattr(node, "final_reflection", "") or "")

    if node_type_upper not in ["OBJECTIVE", "KEY_RESULT"]:
        return new_state, new_reflection

    st_module.markdown("---")
    st_module.caption("Lifecycle & Closing")
    s_col1, _s_col2 = st_module.columns(2)

    allowed_next = list(get_allowed_transitions_fn(current_state) or [])
    options = [current_state] + [
        state for state in allowed_next if state != current_state
    ]
    state_value_options = [state.value for state in options]
    label_map = {
        state.value: f"{state_icons.get(state, '')} {state.value.title()}"
        for state in options
    }

    new_state_val = s_col1.selectbox(
        "Lifecycle State",
        options=state_value_options,
        format_func=lambda value: label_map.get(value, value),
        index=0,
        key=f"state_sel_{node_id}",
        help="Transition rules are enforced. Draft -> Active -> Grading -> Archived.",
    )
    new_state = lifecycle_state_enum(new_state_val)

    st_module.info(f"**{new_state.value.title()}**: {state_hints.get(new_state, '')}")
    if node_type_upper == "OBJECTIVE" and new_state != current_state:
        st_module.warning(
            f"Changing this Objective to **{new_state.value.title()}** will also update all its Key Results."
        )

    new_reflection = str(
        st_module.text_area(
            "Final Reflection",
            value=new_reflection,
            placeholder="What did we learn? Why did we (or didn't we) achieve this?",
            key=f"reflection_{node_id}",
        )
        or ""
    )
    return new_state, new_reflection
