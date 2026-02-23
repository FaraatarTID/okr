"""Helpers for report PDF/HTML export actions."""

from __future__ import annotations

from typing import Any, Callable


def _kr_to_dict(
    *,
    kr: Any,
    json_loads_fn: Callable[[str], Any],
    logger: Any,
) -> dict[str, Any]:
    ga = getattr(kr, "gemini_analysis", None)
    ga_dict = None
    if isinstance(ga, str):
        try:
            ga_dict = json_loads_fn(ga)
        except Exception as exc:
            if logger is not None:
                logger.debug("Failed to parse KR analysis JSON for PDF export: %s", exc)
            ga_dict = None
    elif isinstance(ga, dict):
        ga_dict = ga
    return {
        "title": getattr(kr, "title", "Untitled"),
        "progress": getattr(kr, "progress", 0),
        "geminiAnalysis": ga_dict,
    }


def render_report_export_controls(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    mode: str,
    period_label: str,
    report_items: list[dict[str, Any]],
    objective_stats: dict[str, Any],
    total_minutes: float,
    krs_list: list[Any],
    achievements: list[str],
    username: str,
    utc_now_naive_fn: Callable[[], Any],
    format_time_fn: Callable[[float], str],
    is_backend_enabled_fn: Callable[[], bool],
    run_job_and_wait_fn: Callable[..., dict[str, Any]],
    generate_weekly_pdf_v2_fn: Callable[..., Any],
    generate_pdf_html_fn: Callable[..., str],
    b64decode_fn: Callable[[str], bytes],
    json_loads_fn: Callable[[str], Any],
    logger: Any,
) -> None:
    try:
        if isinstance(session_state, dict):
            report_direction = session_state.get("report_direction")
            report_summary = session_state.get("report_summary")
        else:
            report_direction = getattr(session_state, "report_direction", None)
            report_summary = session_state.get("report_summary")

        pdf_krs = (
            [
                _kr_to_dict(
                    kr=item,
                    json_loads_fn=json_loads_fn,
                    logger=logger,
                )
                for item in krs_list
            ]
            if mode == "Weekly"
            else []
        )
        pdf_title = "Daily Work Report" if mode == "Daily" else "Weekly Work Report"
        file_date = utc_now_naive_fn().strftime("%Y-%m-%d")
        pdf_bytes = None

        if is_backend_enabled_fn():
            job_result = run_job_and_wait_fn(
                kind="pdf.weekly",
                payload={
                    "report_items": report_items,
                    "objective_stats": objective_stats,
                    "total_time_str": format_time_fn(total_minutes),
                    "key_results": pdf_krs,
                    "direction": report_direction,
                    "title": pdf_title,
                    "time_label": period_label,
                    "report_summary": report_summary,
                    "achievements": achievements,
                    "filename": f"{mode}_Report_{file_date}.pdf",
                },
                actor_username=username,
                timeout_seconds=120,
                poll_seconds=1.0,
            )
            if "error" in job_result:
                st_module.warning(f"Backend PDF job failed: {job_result['error']}")
            else:
                encoded_pdf = str(job_result.get("content_b64") or "").strip()
                if encoded_pdf:
                    pdf_bytes = b64decode_fn(encoded_pdf)
        else:
            pdf_buffer = generate_weekly_pdf_v2_fn(
                report_items,
                objective_stats,
                format_time_fn(total_minutes),
                pdf_krs,
                report_direction,
                title=pdf_title,
                time_label=period_label,
                report_summary=report_summary,
                achievements=achievements,
            )
            if pdf_buffer:
                pdf_bytes = pdf_buffer.getvalue()

        if pdf_bytes:
            st_module.download_button(
                label="📄 Export as PDF",
                data=pdf_bytes,
                file_name=f"{mode}_Report_{file_date}.pdf",
                mime="application/pdf",
                key="report_pdf_download",
            )
            return

        fallback_html = generate_pdf_html_fn(
            report_items,
            objective_stats,
            format_time_fn(total_minutes),
            pdf_krs,
            report_direction,
            title=pdf_title,
            time_label=period_label,
            report_summary=report_summary,
            achievements=achievements,
        )
        st_module.info("PDF engine not available. Download the HTML report instead.")
        st_module.download_button(
            label="📄 Export as HTML",
            data=fallback_html.encode("utf-8"),
            file_name=f"{mode}_Report_{file_date}.html",
            mime="text/html",
            key="report_html_download",
        )
    except Exception as exc:
        st_module.error(f"PDF Generation Error: {exc}")
