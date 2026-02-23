"""Strategy Pulse UI helper routines."""

from __future__ import annotations

from typing import Any, Callable


def _risk_color(risk_label: str) -> str:
    if risk_label == "Healthy":
        return "#2e7d32"
    if risk_label == "Elevated":
        return "#f57f17"
    if risk_label == "High":
        return "#e65100"
    return "#c62828"


def render_strategy_pulse_content(
    *,
    st_module: Any,
    session_state: dict[str, Any],
    username: str,
    get_user_by_username_fn: Callable[[str], Any],
    calculate_burnout_risk_fn: Callable[..., dict[str, Any]],
    detect_strategy_gaps_fn: Callable[..., list[dict[str, Any]]],
    generate_predictive_outlook_fn: Callable[..., dict[str, Any]],
    generate_achievement_portfolio_fn: Callable[..., dict[str, Any]],
    generate_achievement_portfolio_pdf_fn: Callable[..., Any],
    utc_now_naive_fn: Callable[[], Any],
) -> None:
    cycle_id = session_state.get("active_cycle_id")
    if not cycle_id:
        st_module.warning("Please select a cycle to view strategic insights.")
        return

    user_obj = get_user_by_username_fn(username)
    if not user_obj:
        st_module.error("User not found.")
        return

    st_module.markdown("### Strategy Pulse")
    st_module.caption(
        "Advanced insights into execution health and strategic alignment."
    )

    col1, col2 = st_module.columns([1, 1])

    with col1:
        st_module.markdown("#### Workload and Burnout")
        with st_module.spinner("Calculating focus intensity..."):
            burnout = calculate_burnout_risk_fn(user_obj.id, days=14)

        risk_label = str(burnout.get("risk_label", "Healthy"))
        risk_score = int(burnout.get("risk_score", 0) or 0)
        color = _risk_color(risk_label)
        st_module.markdown(
            (
                f'<div style="padding: 20px; border-radius: 10px; background: {color}11; border: 1px solid {color}33;">'
                f'<h2 style="color: {color}; margin: 0;">{risk_label}</h2>'
                f'<p style="margin: 5px 0; color: #666;">Burnout Risk Score: <strong>{risk_score}/100</strong></p>'
                '<div style="margin-top: 10px;">'
                f'<span style="font-size: 13px; margin-right: 15px;">Avg Daily: <strong>{int(burnout.get("avg_daily_minutes", 0) or 0)}m</strong></span>'
                f'<span style="font-size: 13px;">14d Output: <strong>{int(burnout.get("completed_tasks", 0) or 0)} tasks</strong></span>'
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        if risk_score > 50:
            st_module.warning(
                "High effort detected relative to output velocity. Consider task pruning or workload redistribution."
            )

    with col2:
        st_module.markdown("#### Ghost Goals and Gaps")
        with st_module.spinner("Scanning for alignment gaps..."):
            gaps = detect_strategy_gaps_fn(cycle_id, user_ids=[user_obj.id])

        if not gaps:
            st_module.success("All active objectives show healthy task activity.")
        else:
            for gap in gaps:
                with st_module.expander(
                    f"Gap: {str(gap.get('title') or 'Untitled')}",
                    expanded=True,
                ):
                    st_module.write(gap.get("detail", "No additional detail provided."))
                    st_module.caption(
                        f"Progress: {gap.get('progress', 0)}% | "
                        f"Type: {gap.get('gap_type', 'N/A')} | "
                        f"Severity: {gap.get('severity', 'N/A')}"
                    )

    st_module.markdown("---")
    st_module.markdown("#### AI Predictive Outlook")
    if st_module.button("Generate Strategic Forecast", type="primary"):
        with st_module.spinner("AI is synthesizing insights..."):
            outlook = generate_predictive_outlook_fn(
                burnout_data=burnout,
                strategy_gaps=gaps,
                cycle_title=f"Cycle {cycle_id}",
            )
            if "error" in outlook:
                st_module.error(str(outlook["error"]))
            else:
                session_state["strategy_outlook"] = outlook

    outlook = session_state.get("strategy_outlook")
    if outlook:
        with st_module.container(border=True):
            st_module.markdown(
                f"**Confidence:** {outlook.get('confidence_level', 'N/A')}"
            )
            st_module.markdown(
                outlook.get("outlook_markdown")
                or outlook.get("outlook_summary")
                or "No forecast generated."
            )
            with st_module.expander("Risk Mitigation Steps"):
                for step in (
                    outlook.get("mitigation_steps")
                    or outlook.get("risk_mitigation")
                    or []
                ):
                    st_module.markdown(f"- {step}")
            pivots = outlook.get("strategic_pivots") or []
            if pivots:
                with st_module.expander("Strategic Pivots"):
                    for pivot in pivots:
                        st_module.markdown(f"- {pivot}")

    st_module.markdown("---")
    st_module.markdown("#### Achievement Portfolio")
    col_port1, col_port2 = st_module.columns([2, 1])
    with col_port1:
        st_module.caption(
            "Generate a professional summary of high-impact contributions for this cycle."
        )

    with col_port2:
        if st_module.button("Prepare Portfolio PDF", use_container_width=True):
            with st_module.spinner("Aggregating achievements..."):
                portfolio = generate_achievement_portfolio_fn(
                    user_id=user_obj.id,
                    cycle_id=cycle_id,
                    user_display_name=user_obj.display_name or user_obj.username,
                )
                pdf_bytes = generate_achievement_portfolio_pdf_fn(portfolio)
                if pdf_bytes:
                    session_state["portfolio_pdf"] = pdf_bytes.getvalue()
                    session_state["portfolio_filename"] = (
                        f"Portfolio_{username}_{utc_now_naive_fn().strftime('%Y%m%d')}.pdf"
                    )
                    st_module.success("Portfolio ready!")
                else:
                    st_module.error(
                        "Failed to generate PDF. Check PDF engine configuration."
                    )

    if "portfolio_pdf" in session_state:
        st_module.download_button(
            label="Download Achievement Portfolio",
            data=session_state["portfolio_pdf"],
            file_name=session_state["portfolio_filename"],
            mime="application/pdf",
            use_container_width=True,
        )
