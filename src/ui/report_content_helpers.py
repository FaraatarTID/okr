"""Report content rendering helpers."""

from __future__ import annotations

import time

from src.ui import report_content_sections_helpers


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
    escape_html_fn=None,
    calculate_kr_score_fn,
    get_score_label_fn,
    get_score_color_band_fn,
    report_helpers_module,
    report_export_helpers_module,
    report_kr_status_helpers_module,
    logger,
):
    """Render report dialog content for daily/weekly modes."""
    if escape_html_fn is None:
        from src.ui.safe_html import escape_html as _escape_html

        escape_html_fn = _escape_html

    now = time.time() * 1000
    start_time, period_label = report_content_sections_helpers.resolve_report_window(
        mode=mode,
        now_millis=now,
        from_epoch_millis_fn=from_epoch_millis_fn,
    )

    report_content_sections_helpers.render_report_header_controls(
        st_module=st_module,
        mode=mode,
        period_label=period_label,
    )

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

    report_content_sections_helpers.render_executive_summary_section(
        st_module=st_module,
        mode=mode,
        username=username,
        start_time_millis=start_time,
        from_epoch_millis_fn=from_epoch_millis_fn,
        utc_now_naive_fn=utc_now_naive_fn,
        report_items=report_items,
        objective_stats=objective_stats,
        achievements=achievements,
        total_minutes=total,
        format_time_fn=format_time_fn,
    )

    st_module.markdown("---")

    report_content_sections_helpers.render_trends_and_achievements_section(
        st_module=st_module,
        mode=mode,
        daily_minutes=daily_minutes,
        achievements=achievements,
    )
    report_content_sections_helpers.render_deadline_health_section(
        st_module=st_module,
        cycle_task_scan_limit_fn=cycle_task_scan_limit_fn,
        cached_get_all_tasks_by_cycle_fn=cached_get_all_tasks_by_cycle_fn,
        get_deadline_status_fn=get_deadline_status,
        logger=logger,
    )

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

    report_content_sections_helpers.render_detailed_work_log_section(
        st_module=st_module,
        report_items=report_items,
        escape_html_fn=escape_html_fn,
    )
    report_content_sections_helpers.render_objective_distribution_section(
        st_module=st_module,
        period_label=period_label,
        total_minutes=total,
        objective_stats=objective_stats,
        format_time_fn=format_time_fn,
        escape_html_fn=escape_html_fn,
    )

    # --- SECTION: Key Result Strategic Status (Weekly Only) ---
    from src.crud import update_key_result
    from src.services.ai_service import analyze_node

    should_abort_report = (
        report_kr_status_helpers_module.render_weekly_kr_strategic_status(
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
    )
    if should_abort_report:
        return
