"""Section helpers for report content rendering."""

from __future__ import annotations

from typing import Any, Callable

from src.ui import dialog_chrome_helpers
from src.ui import session_keys


def resolve_report_window(
    *,
    mode: str,
    now_millis: float,
    from_epoch_millis_fn: Callable[[float], Any],
) -> tuple[float, str]:
    """Compute report start-time window and user-facing period label."""
    if mode == "Daily":
        dt_now = from_epoch_millis_fn(now_millis)
        dt_start = dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return float(dt_start.timestamp() * 1000), "Today"

    start_time = now_millis - (7 * 24 * 60 * 60 * 1000)
    return float(start_time), "Last 7 Days"


def render_report_header_controls(
    *,
    st_module: Any,
    mode: str,
    period_label: str,
) -> None:
    """Render report dialog chrome, direction selector, and close control."""
    dialog_chrome_helpers.apply_standard_dialog_chrome(st_module=st_module)
    st_module.markdown(
        """
        <style>
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button:hover {
            border-color: #ff4b4b;
            color: #ff4b4b;
            background-color: #fff5f5;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    c_head, c_opts, c_close = st_module.columns([2, 1, 0.5])
    c_head.caption(f"Tasks with work recorded for: {mode} ({period_label})")

    if session_keys.REPORT_DIRECTION not in st_module.session_state:
        st_module.session_state[session_keys.REPORT_DIRECTION] = "LTR"

    with c_opts:
        st_module.session_state[session_keys.REPORT_DIRECTION] = (
            st_module.segmented_control(
                "PDF Direction",
                options=["LTR", "RTL"],
                default=st_module.session_state[session_keys.REPORT_DIRECTION],
                key=f"rep_dir_{mode}",
                label_visibility="collapsed",
            )
        )

    with c_close:
        if st_module.button("✕", key=f"close_rep_{mode}"):
            if session_keys.ACTIVE_REPORT_MODE in st_module.session_state:
                del st_module.session_state[session_keys.ACTIVE_REPORT_MODE]
            st_module.rerun()


def render_executive_summary_section(
    *,
    st_module: Any,
    mode: str,
    username: str,
    start_time_millis: float,
    from_epoch_millis_fn: Callable[[float], Any],
    utc_now_naive_fn: Callable[[], Any],
    report_items: list[dict[str, Any]],
    objective_stats: dict[str, Any],
    achievements: list[str],
    total_minutes: float,
    format_time_fn: Callable[[float], str],
) -> None:
    """Render weekly executive summary card and AI brief flow."""
    if mode == "Daily":
        return

    with st_module.container():
        st_module.markdown("### 📋 Executive Summary")

        if session_keys.REPORT_SUMMARY not in st_module.session_state:
            if st_module.button(
                "✨ Generate AI Weekly Brief", type="primary", key="report_gen_ai"
            ):
                with st_module.spinner("Drafting executive summary..."):
                    from src.services.ai_service import generate_weekly_summary

                    krs_updated = len(
                        {str(item.get("KeyResult", "")) for item in report_items}
                    )
                    obj_summary = [
                        f"{key}: {int(value)}m"
                        for key, value in objective_stats.items()
                    ]

                    stats = {
                        "total_minutes": total_minutes,
                        "tasks_completed": len(achievements),
                        "krs_updated": krs_updated,
                        "objectives_text": obj_summary,
                        "key_achievements": list(achievements),
                        "work_logs_text": "\n".join(
                            [
                                f"{item.get('Task', '')}: {item.get('Summary', '')}"
                                for item in report_items[:30]
                            ]
                        ),
                    }

                    result = generate_weekly_summary(
                        username,
                        from_epoch_millis_fn(start_time_millis).strftime("%Y-%m-%d"),
                        utc_now_naive_fn().strftime("%Y-%m-%d"),
                        stats,
                    )

                    if "error" not in result:
                        st_module.session_state[session_keys.REPORT_SUMMARY] = result
                        st_module.rerun()
                    else:
                        st_module.error(result["error"])

        summary_result = st_module.session_state.get(session_keys.REPORT_SUMMARY)
        if summary_result:
            st_module.markdown(summary_result.get("summary_markdown"))

            m1, m2, m3 = st_module.columns(3)
            m1.metric("Total Focus", format_time_fn(total_minutes))
            m2.metric("Tasks Completed", len(achievements))
            m3.metric("Key Highlights", len(summary_result.get("highlights", [])))

            with st_module.expander("📌 Highlights"):
                for highlight in summary_result.get("highlights", []):
                    st_module.markdown(f"- {highlight}")
        else:
            st_module.info("Click above to generate an executive brief of your week.")


def render_trends_and_achievements_section(
    *,
    st_module: Any,
    mode: str,
    daily_minutes: dict[str, Any],
    achievements: list[str],
) -> None:
    """Render weekly trends chart and achievements panel."""
    c_trend, c_achieve = st_module.columns([1.5, 1])

    with c_trend:
        if mode != "Daily":
            st_module.subheader("📈 Weekly Trends")
            if daily_minutes:
                sorted_dates = sorted(daily_minutes.keys())
                chart_data = {
                    "Date": sorted_dates,
                    "Hours": [float(daily_minutes[d]) / 60 for d in sorted_dates],
                }
                st_module.bar_chart(chart_data, x="Date", y="Hours", color="#4CAF50")
            else:
                st_module.caption("No trend data available.")
        else:
            st_module.info("Trend analysis available in Weekly Report.")

    with c_achieve:
        st_module.subheader("🏆 Achievements")
        if achievements:
            for achievement in achievements:
                st_module.success(f"✅ {achievement}")
        else:
            st_module.caption("No completed tasks this period.")


def render_deadline_health_section(
    *,
    st_module: Any,
    cycle_task_scan_limit_fn: Callable[[], int],
    cached_get_all_tasks_by_cycle_fn: Callable[..., list[Any]],
    get_deadline_status_fn: Callable[[Any], tuple[Any, str, Any]],
    logger: Any,
) -> None:
    """Render deadline health warnings for the active cycle."""
    st_module.subheader("⚠️ Deadline Health")
    cycle_id = st_module.session_state.get("active_cycle_id")
    task_scan_limit = int(cycle_task_scan_limit_fn() or 0)
    tasks = list(
        cached_get_all_tasks_by_cycle_fn(cycle_id, limit=task_scan_limit) or []
    )

    warnings: list[str] = []
    for task in tasks:
        if (
            getattr(task, "deadline", None)
            and int(getattr(task, "progress", 0) or 0) < 100
        ):
            try:
                _, label, _ = get_deadline_status_fn(task)
                if "Overdue" in str(label) or "At Risk" in str(label):
                    warnings.append(f"{label} - {getattr(task, 'title', 'Untitled')}")
            except Exception as exc:
                if logger is not None:
                    logger.debug(
                        "Failed to evaluate deadline warning for task %s: %s",
                        getattr(task, "id", None),
                        exc,
                    )

    if warnings:
        if len(tasks) >= task_scan_limit:
            st_module.caption(
                f"Showing deadline warnings from first {task_scan_limit} tasks in this cycle."
            )
        for warning_text in warnings[:5]:
            st_module.error(warning_text)
        if len(warnings) > 5:
            st_module.caption(f"...and {len(warnings) - 5} more.")
    else:
        st_module.success("All tasks on track!", icon="🟢")


def render_detailed_work_log_section(
    *,
    st_module: Any,
    report_items: list[dict[str, Any]],
    escape_html_fn: Callable[[str], str],
) -> None:
    """Render detailed work-log table."""
    st_module.markdown("---")
    st_module.subheader("📝 Detailed Work Log")

    report_items.sort(
        key=lambda item: f"{item.get('Date', '')}{item.get('Time', '')}", reverse=True
    )
    if not report_items:
        return

    table_html = """<table style="width:100%; border-collapse: collapse; font-family: 'Vazirmatn', sans-serif; font-size: 0.85em;">
            <thead>
                <tr style="border-bottom: 2px solid #ddd; background-color: #f8f9fa;">
                    <th style="padding: 8px; text-align: left; width: 20%;">Task</th>
                    <th style="padding: 8px; text-align: left; width: 15%;">Objective</th>
                    <th style="padding: 8px; text-align: left; width: 15%;">Key Result</th>
                    <th style="padding: 8px; text-align: left;">Date</th>
                    <th style="padding: 8px; text-align: right;">Time</th>
                    <th style="padding: 8px; text-align: left; width: 25%;">Summary</th>
                </tr>
            </thead>
            <tbody>"""

    for item in report_items:
        summary_txt = escape_html_fn(str(item.get("Summary", "")))
        task_txt = escape_html_fn(str(item.get("Task", "")))
        objective_txt = escape_html_fn(str(item.get("Objective", "")))
        kr_txt = escape_html_fn(str(item.get("KeyResult", "")))
        date_txt = escape_html_fn(str(item.get("Date", "")))
        time_txt = escape_html_fn(str(item.get("Time", "")))
        duration_txt = escape_html_fn(str(item.get("Duration (m)", "0")))

        table_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px;">{task_txt}</td>
                     <td style="padding: 8px; color: #555;">{objective_txt}</td>
                     <td style="padding: 8px; color: #555;">{kr_txt}</td>
                    <td style="padding: 8px; white-space: nowrap;">{date_txt} {time_txt}</td>
                    <td style="padding: 8px; text-align: right;">{duration_txt}m</td>
                    <td style="padding: 8px; color: #555;">{summary_txt}</td>
                </tr>"""

    table_html += "</tbody></table>"
    st_module.markdown(table_html, unsafe_allow_html=True)


def render_objective_distribution_section(
    *,
    st_module: Any,
    period_label: str,
    total_minutes: float,
    objective_stats: dict[str, Any],
    format_time_fn: Callable[[float], str],
    escape_html_fn: Callable[[str], str],
) -> None:
    """Render total time metric and objective distribution table."""
    st_module.metric(f"Total Time ({period_label})", format_time_fn(total_minutes))
    st_module.markdown("---")
    st_module.subheader("Time Distribution by Objective")

    sorted_stats = sorted(
        objective_stats.items(),
        key=lambda item: float(item[1] or 0),
        reverse=True,
    )

    table_html = """<table style="width:100%; border-collapse: collapse; font-family: 'Vazirmatn', sans-serif; font-size: 0.95em;">
        <thead>
            <tr style="border-bottom: 2px solid #ddd; background-color: #f8f9fa;">
                <th style="padding: 8px; text-align: left;">Objective</th>
                <th style="padding: 8px; text-align: right;">Time</th>
                <th style="padding: 8px; text-align: right;">%</th>
            </tr>
        </thead>
        <tbody>"""

    for objective, minutes in sorted_stats:
        minutes_float = float(minutes or 0)
        percentage = (minutes_float / total_minutes * 100) if total_minutes > 0 else 0
        p_str = f"{percentage:.1f}%"
        t_str = format_time_fn(minutes_float)
        objective_txt = escape_html_fn(str(objective))
        table_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px;">{objective_txt}</td>
                <td style="padding: 8px; text-align: right;">{t_str}</td>
                <td style="padding: 8px; text-align: right;">{p_str}</td>
            </tr>"""

    table_html += "</tbody></table>"
    st_module.markdown(table_html, unsafe_allow_html=True)
