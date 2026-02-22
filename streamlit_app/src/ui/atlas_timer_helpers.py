"""Timer panel rendering helpers."""

from __future__ import annotations

from typing import Any, Callable


def render_timer_content(
    *,
    st_module: Any,
    node_id: Any,
    username: str,
    load_task_fn: Callable[[Any], Any],
    stop_timer_fn: Callable[..., Any],
    fetch_latest_logs_fn: Callable[[Any], list[Any]],
    ensure_utc_fn: Callable[[Any], Any],
    utc_now_naive_fn: Callable[[], Any],
    escape_html_fn: Callable[[str], str],
) -> None:
    node = load_task_fn(node_id)
    if not node:
        st_module.error("Task not found")
        return

    safe_title = escape_html_fn(str(getattr(node, "title", "") or ""))
    st_module.markdown(
        f"<div class='timer-task-title'>{safe_title}</div>",
        unsafe_allow_html=True,
    )
    st_module.markdown(
        "<div class='timer-subtext'>Focus on this task and record your flow.</div>",
        unsafe_allow_html=True,
    )

    placeholder = st_module.empty()
    _left_col, action_col, _right_col = st_module.columns([1, 1, 1])
    start_ts = getattr(node, "timer_started_at", None)

    if start_ts:
        now = ensure_utc_fn(utc_now_naive_fn())
        elapsed = now - ensure_utc_fn(start_ts)
        elapsed_sec = int(elapsed.total_seconds())

        h = elapsed_sec // 3600
        m = (elapsed_sec % 3600) // 60
        s = elapsed_sec % 60
        placeholder.markdown(
            f"<div class='timer-display'>{h:02d}:{m:02d}:{s:02d}</div>",
            unsafe_allow_html=True,
        )
        st_module.caption(
            "Elapsed time is calculated from the stored start timestamp and updates when the view rerenders."
        )

        summary = st_module.text_input(
            "What did you work on?",
            placeholder="e.g. Drafted initial outline...",
            key=f"timer_sum_{node_id}",
        )
        if action_col.button("✋ Stop & Log", type="primary", use_container_width=True):
            wl = stop_timer_fn(node_id, summary=summary, user_id=username)
            if wl:
                logs = list(fetch_latest_logs_fn(node_id) or [])
                st_module.success(f"Logged {round(float(wl.duration_minutes), 1)} minutes")
                if logs:
                    latest = logs[0]
                    st_module.info(
                        f"Last log: {latest.start_time.strftime('%Y-%m-%d %H:%M')} — {round(float(latest.duration_minutes), 1)}m — {latest.summary or '-'}"
                    )
            else:
                st_module.warning("No running timer found for this task.")
            if "active_timer_node_id" in st_module.session_state:
                del st_module.session_state["active_timer_node_id"]
            st_module.rerun()
        return

    placeholder.markdown(
        "<div class='timer-display'>00:00:00</div>",
        unsafe_allow_html=True,
    )
    st_module.warning("Timer is not running.")
    if action_col.button("Close", use_container_width=True):
        if "active_timer_node_id" in st_module.session_state:
            del st_module.session_state["active_timer_node_id"]
        st_module.rerun()
