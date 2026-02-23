"""Task-specific inspector form sections."""

from __future__ import annotations

from typing import Any, Callable


def render_task_schedule_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    node_id: int,
    username: str,
    update_task_fn: Callable[..., Any],
    datetime_cls: Any,
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    rerun_fn: Callable[[], Any],
    logger: Any,
) -> bool:
    """Render task scheduling/deadline controls.

    Returns True when caller should abort due to an error.
    """
    if node_type_upper != "TASK":
        return False

    st_module.markdown("---")
    st_module.write("### Schedule")

    curr_sd = (
        node.start_date.date()
        if isinstance(getattr(node, "start_date", None), datetime_cls)
        else None
    )
    curr_d = (
        node.deadline.date()
        if isinstance(getattr(node, "deadline", None), datetime_cls)
        else None
    )

    col_sch1, col_sch2 = st_module.columns(2)
    with col_sch1:
        new_sd = st_module.date_input(
            "Start Date", value=curr_sd, key=f"sd_inp_{node_id}"
        )
        if st_module.button("Save Start Date", key=f"save_sd_{node_id}"):
            new_sd_dt = (
                datetime_cls.combine(new_sd, datetime_cls.min.time())
                if new_sd
                else None
            )
            try:
                update_task_fn(node_id, start_date=new_sd_dt, actor_username=username)
            except PermissionError as exc:
                st_module.error(str(exc))
                return True
            rerun_fn()

    with col_sch2:
        new_d = st_module.date_input("Due Date", value=curr_d, key=f"dl_inp_{node_id}")
        if st_module.button("Save Due Date", key=f"save_dl_{node_id}"):
            new_dl_dt = (
                datetime_cls.combine(new_d, datetime_cls.max.time()) if new_d else None
            )
            try:
                update_task_fn(node_id, deadline=new_dl_dt, actor_username=username)
            except PermissionError as exc:
                st_module.error(str(exc))
                return True
            rerun_fn()

    clr1, clr2 = st_module.columns(2)
    if curr_sd and clr1.button("Clear Start", key=f"clear_sd_{node_id}"):
        try:
            update_task_fn(node_id, start_date=None, actor_username=username)
        except PermissionError as exc:
            st_module.error(str(exc))
            return True
        rerun_fn()

    has_deadline = getattr(node, "deadline", None) is not None
    if has_deadline and clr2.button("Clear Due", key=f"clear_dl_{node_id}"):
        try:
            update_task_fn(node_id, deadline=None, actor_username=username)
        except PermissionError as exc:
            st_module.error(str(exc))
            return True
        rerun_fn()

    if has_deadline:
        try:
            _status_code, status_label, health = get_deadline_status_fn(node)
            st_module.metric("Deadline Status", status_label)
            st_module.progress(float(health) / 100.0)
        except Exception as exc:
            if logger is not None:
                logger.debug(
                    "Failed to compute inspector deadline status for node %s: %s",
                    node_id,
                    exc,
                )

    return False


def render_task_work_history_section(
    *,
    st_module: Any,
    node: Any,
    node_type_upper: str,
    username: str,
    get_work_logs_fn: Callable[[Any], list[Any]],
    delete_work_log_fn: Callable[..., Any],
    rerun_fn: Callable[[], Any],
    datetime_cls: Any,
) -> bool:
    """Render task work-history list and delete actions.

    Returns True when caller should abort due to an error.
    """
    if node_type_upper != "TASK":
        st_module.markdown("---")
        st_module.info(
            "Work logs are attached to tasks. Select a task in Focus Map to view its Work History."
        )
        return False

    st_module.markdown("---")
    st_module.markdown("### Work History")
    work_logs = list(get_work_logs_fn(getattr(node, "id", None)) or [])
    st_module.caption(f"Work logs found: {len(work_logs)}")

    if not work_logs:
        st_module.info("No work logs found for this task.")
        if st_module.button("Refresh Work History"):
            rerun_fn()
        return False

    sorted_logs = sorted(
        work_logs,
        key=lambda item: getattr(item, "end_time", None) or datetime_cls.min,
        reverse=True,
    )
    for log_item in sorted_logs:
        end_time_value = getattr(log_item, "end_time", None)
        ended_at = (
            end_time_value.strftime("%Y-%m-%d %H:%M") if end_time_value else "Running"
        )
        duration_minutes = round(
            float(getattr(log_item, "duration_minutes", 0) or 0), 1
        )
        summary_text = getattr(log_item, "summary", None) or "-"

        col_l1, col_l2 = st_module.columns([0.9, 0.1])
        col_l1.write(f"**{ended_at}** | {duration_minutes}m | {summary_text}")
        if col_l2.button("Delete", key=f"del_log_{getattr(log_item, 'id', '')}"):
            try:
                delete_work_log_fn(
                    getattr(log_item, "id", None),
                    actor_username=username,
                )
            except PermissionError as exc:
                st_module.error(str(exc))
                return True
            rerun_fn()

    return False
