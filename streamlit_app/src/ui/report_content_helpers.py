"""Report content rendering helpers."""

from __future__ import annotations

import time

def render_report_content(
    username,
    mode,
    *,
    st_module,
    from_epoch_millis_fn,
    utc_now_naive_fn,
    get_user_by_username_fn,
    cached_get_work_logs_by_range_fn,
    cycle_task_scan_limit_fn,
    cached_get_all_tasks_by_cycle_fn,
    cached_get_all_krs_by_cycle_fn,
    format_time_fn,
    escape_html_fn,
    calculate_kr_score_fn,
    get_score_label_fn,
    get_score_color_band_fn,
    report_helpers_module,
    report_export_helpers_module,
    report_kr_status_helpers_module,
    logger,
):
    # data parameter removed
    # Filter logic
    now = time.time() * 1000
    if mode == "Daily":
        # Start of today
        # Calculate midnight timestamp for today
        dt_now = from_epoch_millis_fn(now)
        dt_start = dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = dt_start.timestamp() * 1000
        period_label = "Today"
    else:
        # Weekly (7 days)
        start_time = now - (7 * 24 * 60 * 60 * 1000)
        period_label = "Last 7 Days"

    # CSS: Style YOUR EXISTING custom button as a circle (Dialog specific)
    st_module.markdown(
        """
        <style>
        /* 1. Hide the Native Close Button */
        div[role="dialog"] button[aria-label="Close"] {
            display: none;
        }

        /* 2. Hide the Native Backdrop (the original close trigger) */
        div[data-baseweb="modal-backdrop"] {
            display: none;
        }

        /* 3. The Visual Background Layer */
        div[data-baseweb="modal"] {
            background-color: rgba(0, 0, 0, 0.5);
            pointer-events: none; 
        }

        /* 4. The "Invisible Click Shield" */
        div[role="dialog"]::before {
            content: "";
            position: absolute;
            top: -500vh;
            left: -500vw;
            width: 1000vw;
            height: 1000vh;
            background: transparent;
            z-index: -1;
            cursor: default;
            pointer-events: auto;
        }

        /* 5. Ensure the Dialog Box is Interactive */
        div[role="dialog"] {
            overflow: visible !important;
            pointer-events: auto;
        }

        /* 6. Style YOUR Custom "X" Button as a Circle */
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            border-radius: 50%;
            border: 1px solid #e0e0e0;
            width: 35px;
            height: 35px;
            padding: 0 !important;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            background-color: white; 
        }
        
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button:hover {
            border-color: #ff4b4b;
            color: #ff4b4b;
            background-color: #fff5f5;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Header with Close Button
    c_head, c_opts, c_close = st_module.columns([2, 1, 0.5])
    c_head.caption(f"Tasks with work recorded for: {mode} ({period_label})")

    # PDF Direction Toggle
    if "report_direction" not in st_module.session_state:
        st_module.session_state.report_direction = "LTR"

    with c_opts:
        st_module.session_state.report_direction = st_module.segmented_control(
            "PDF Direction",
            options=["LTR", "RTL"],
            default=st_module.session_state.report_direction,
            key=f"rep_dir_{mode}",
            label_visibility="collapsed",
        )

    with c_close:
        if st_module.button("✕", key=f"close_rep_{mode}"):
            if "active_report_mode" in st_module.session_state:
                del st_module.session_state.active_report_mode
            st_module.rerun()

    user_obj = get_user_by_username_fn(username)
    if not user_obj:
        st_module.error("User not found")
        return

    start_dt = from_epoch_millis_fn(start_time)
    end_dt = from_epoch_millis_fn(now)

    logs = cached_get_work_logs_by_range_fn(user_obj.id, start_dt, end_dt)

    if not logs:
        st_module.info("No work recorded in this period.")
        return

    from src.utils.deadline_utils import get_deadline_status

    report_payload = report_helpers_module.build_report_payload(
        logs=list(logs),
        get_deadline_status_fn=get_deadline_status,
        logger=logger,
    )
    report_items = list(report_payload.get("report_items") or [])
    objective_stats = dict(report_payload.get("objective_stats") or {})
    daily_minutes = dict(report_payload.get("daily_minutes") or {})
    achievements = list(report_payload.get("achievements") or [])
    total = float(report_payload.get("total_minutes") or 0)

    # === EXECUTIVE SUMMARY CARD ===
    if mode != "Daily":
        with st_module.container():
            st_module.markdown("### 📋 Executive Summary")

            # AI Summary
            if "report_summary" not in st_module.session_state:
                if st_module.button(
                    "✨ Generate AI Weekly Brief", type="primary", key="report_gen_ai"
                ):
                    with st_module.spinner("Drafting executive summary..."):
                        from src.services.ai_service import generate_weekly_summary

                        # Prepare context
                        krs_updated = len(set(i["KeyResult"] for i in report_items))
                        obj_summary = [
                            f"{k}: {int(v)}m" for k, v in objective_stats.items()
                        ]

                        stats = {
                            "total_minutes": total,
                            "tasks_completed": len(achievements),
                            "krs_updated": krs_updated,
                            "objectives_text": obj_summary,
                            "key_achievements": achievements,
                            "work_logs_text": "\n".join(
                                [
                                    f"{i['Task']}: {i['Summary']}"
                                    for i in report_items[:30]
                                ]
                            ),
                        }

                        res = generate_weekly_summary(
                            username,
                            from_epoch_millis_fn(start_time).strftime(
                                "%Y-%m-%d"
                            ),
                            utc_now_naive_fn().strftime("%Y-%m-%d"),
                            stats,
                        )

                        if "error" not in res:
                            st_module.session_state.report_summary = res
                            st_module.rerun()
                        else:
                            st_module.error(res["error"])

            summary_res = st_module.session_state.get("report_summary")
            if summary_res:
                st_module.markdown(summary_res.get("summary_markdown"))

                # Metrics Row
                m1, m2, m3 = st_module.columns(3)
                m1.metric("Total Focus", format_time_fn(total))
                m2.metric("Tasks Completed", len(achievements))
                m3.metric("Key Highlights", len(summary_res.get("highlights", [])))

                with st_module.expander("📌 Highlights"):
                    for h in summary_res.get("highlights", []):
                        st_module.markdown(f"- {h}")
            else:
                st_module.info("Click above to generate an executive brief of your week.")

    st_module.markdown("---")

    # === TRENDS & ANALYSIS ===
    c_trend, c_achieve = st_module.columns([1.5, 1])

    with c_trend:
        if mode != "Daily":
            st_module.subheader("📈 Weekly Trends")
            if daily_minutes:
                # Sort dates
                sorted_dates = sorted(daily_minutes.keys())
                chart_data = {
                    "Date": sorted_dates,
                    "Hours": [daily_minutes[d] / 60 for d in sorted_dates],
                }
                st_module.bar_chart(chart_data, x="Date", y="Hours", color="#4CAF50")
            else:
                st_module.caption("No trend data available.")
        else:
            st_module.info("Trend analysis available in Weekly Report.")

    with c_achieve:
        st_module.subheader("🏆 Achievements")
        if achievements:
            for ach in achievements:
                st_module.success(f"✅ {ach}")
        else:
            st_module.caption("No completed tasks this period.")

    # Deadline Health
    st_module.subheader("⚠️ Deadline Health")
    cycle_id_dl = st_module.session_state.get("active_cycle_id")
    task_scan_limit = cycle_task_scan_limit_fn()
    tasks_dl = cached_get_all_tasks_by_cycle_fn(cycle_id_dl, limit=task_scan_limit)

    warnings_dl = []
    for t_dl in tasks_dl:
        if t_dl.deadline and t_dl.progress < 100:
            try:
                _, label_dl, _ = get_deadline_status(t_dl)
                if "Overdue" in label_dl or "At Risk" in label_dl:
                    warnings_dl.append(f"{label_dl} - {t_dl.title}")
            except Exception as exc:
                logger.debug("Failed to evaluate deadline warning for task %s: %s", t_dl.id, exc)

    if warnings_dl:
        if len(tasks_dl) >= task_scan_limit:
            st_module.caption(
                f"Showing deadline warnings from first {task_scan_limit} tasks in this cycle."
            )
        for w in warnings_dl[:5]:
            st_module.error(w)
        if len(warnings_dl) > 5:
            st_module.caption(f"...and {len(warnings_dl) - 5} more.")
    else:
        st_module.success("All tasks on track!", icon="🟢")

    cycle_id_krs = st_module.session_state.get("active_cycle_id")
    krs_list = cached_get_all_krs_by_cycle_fn(cycle_id_krs)

    # PDF Export (Moved to Top)
    from src.services.pdf_service import generate_pdf_html, generate_weekly_pdf_v2
    from src.services.backend_client import is_backend_enabled
    from src.services.job_service import run_job_and_wait
    import base64
    import json

    report_export_helpers_module.render_report_export_controls(
        st_module=st_module,
        session_state=st_module.session_state,
        mode=mode,
        period_label=period_label,
        report_items=report_items,
        objective_stats=objective_stats,
        total_minutes=total,
        krs_list=list(krs_list),
        achievements=list(achievements),
        username=username,
        utc_now_naive_fn=utc_now_naive_fn,
        format_time_fn=format_time_fn,
        is_backend_enabled_fn=is_backend_enabled,
        run_job_and_wait_fn=run_job_and_wait,
        generate_weekly_pdf_v2_fn=generate_weekly_pdf_v2,
        generate_pdf_html_fn=generate_pdf_html,
        b64decode_fn=base64.b64decode,
        json_loads_fn=json.loads,
        logger=logger,
    )

    st_module.markdown("---")
    st_module.subheader("📝 Detailed Work Log")

    # Sort items for display
    report_items.sort(key=lambda x: x["Date"] + x["Time"], reverse=True)

    # Using HTML table to ensure font consistency
    if report_items:
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
        for itm in report_items:
            summary_txt = escape_html_fn(itm.get("Summary", ""))
            task_txt = escape_html_fn(itm.get("Task", ""))
            objective_txt = escape_html_fn(itm.get("Objective", ""))
            kr_txt = escape_html_fn(itm.get("KeyResult", ""))
            date_txt = escape_html_fn(itm.get("Date", ""))
            time_txt = escape_html_fn(itm.get("Time", ""))
            duration_txt = escape_html_fn(itm.get("Duration (m)", "0"))

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

    st_module.metric(f"Total Time ({period_label})", format_time_fn(total))

    st_module.markdown("---")
    st_module.subheader("Time Distribution by Objective")

    # Prepare data for chart/table
    # Sort stats by minutes descending first
    sorted_stats_obj = sorted(
        objective_stats.items(), key=lambda item: item[1], reverse=True
    )

    # Using HTML table for objectives too
    obj_table_h = """<table style="width:100%; border-collapse: collapse; font-family: 'Vazirmatn', sans-serif; font-size: 0.95em;">
        <thead>
            <tr style="border-bottom: 2px solid #ddd; background-color: #f8f9fa;">
                <th style="padding: 8px; text-align: left;">Objective</th>
                <th style="padding: 8px; text-align: right;">Time</th>
                <th style="padding: 8px; text-align: right;">%</th>
            </tr>
        </thead>
        <tbody>"""

    for t_obj, mins_obj in sorted_stats_obj:
        percentage_obj = (mins_obj / total * 100) if total > 0 else 0
        p_str_obj = f"{percentage_obj:.1f}%"
        t_str_obj = format_time_fn(mins_obj)
        objective_txt = escape_html_fn(t_obj)

        obj_table_h += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px;">{objective_txt}</td>
                <td style="padding: 8px; text-align: right;">{t_str_obj}</td>
                <td style="padding: 8px; text-align: right;">{p_str_obj}</td>
            </tr>"""
    obj_table_h += "</tbody></table>"
    st_module.markdown(obj_table_h, unsafe_allow_html=True)

    # --- SECTION: Key Result Strategic Status (Weekly Only) ---
    from src.crud import update_key_result
    from src.services.ai_service import analyze_node

    should_abort_report = report_kr_status_helpers_module.render_weekly_kr_strategic_status(
        st_module=st_module,
        mode=mode,
        krs_list=list(krs_list),
        username=username,
        calculate_kr_score_fn=calculate_kr_score_fn,
        get_score_label_fn=get_score_label_fn,
        get_score_color_band_fn=get_score_color_band_fn,
        analyze_node_fn=analyze_node,
        update_key_result_fn=update_key_result,
        json_loads_fn=json.loads,
        logger=logger,
    )
    if should_abort_report:
        return
