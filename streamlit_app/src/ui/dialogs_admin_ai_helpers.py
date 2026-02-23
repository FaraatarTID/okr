"""Admin-panel AI health tab helpers."""

from __future__ import annotations

import json

import streamlit as st


def render_ai_health_tab_content() -> None:
    """Render the admin AI provider health tab."""
    from src.services.ai_provider import (
        get_ai_provider_runtime_status,
        is_external_ai_allowed,
        run_ai_health_check,
    )

    st.markdown("#### AI Provider Health")
    st.caption(
        "Validate AI provider configuration and optionally run a live model probe."
    )

    status = get_ai_provider_runtime_status()
    c_status_1, c_status_2, c_status_3 = st.columns(3)
    c_status_1.metric("Provider", status.provider)
    c_status_2.metric("Configured", "Yes" if status.ready else "No")
    c_status_3.metric(
        "External AI",
        "Enabled" if is_external_ai_allowed() else "Disabled",
    )

    if status.ready:
        st.info(status.message)
    else:
        st.warning(status.message)

    c_probe_1, c_probe_2 = st.columns(2)
    if c_probe_1.button("Check Config Only", key="admin_ai_check_config"):
        st.session_state["admin_ai_health_report"] = run_ai_health_check(
            live_probe=False
        )
        st.rerun()

    if c_probe_2.button("Run Live Probe", key="admin_ai_check_live", type="primary"):
        with st.spinner("Running live AI provider probe..."):
            st.session_state["admin_ai_health_report"] = run_ai_health_check(
                live_probe=True
            )
        st.rerun()

    report = st.session_state.get("admin_ai_health_report")
    if report:
        report_status = str(report.get("status") or "").strip().lower()
        if report_status in {"ok", "configured", "disabled"}:
            st.success(f"Status: {report_status}")
        elif report_status in {"not_configured", "probe_failed"}:
            st.error(f"Status: {report_status}")
        else:
            st.info(f"Status: {report_status or 'unknown'}")

        st.json(report)
        report_json = json.dumps(report, indent=2, ensure_ascii=False)
        st.download_button(
            label="Download Health Report",
            data=report_json.encode("utf-8"),
            file_name="ai_provider_health_report.json",
            mime="application/json",
            key="admin_ai_health_download",
        )
