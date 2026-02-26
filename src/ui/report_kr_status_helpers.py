"""Helpers for weekly Key Result strategic status rendering."""

from __future__ import annotations

from typing import Any, Callable


def _analysis_dict(
    *,
    analysis_raw: Any,
    json_loads_fn: Callable[[str], Any],
    logger: Any,
) -> dict[str, Any] | None:
    if isinstance(analysis_raw, dict):
        return analysis_raw
    if isinstance(analysis_raw, str) and analysis_raw.strip():
        try:
            parsed = json_loads_fn(analysis_raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            if logger is not None:
                logger.debug("Failed to parse KR analysis score payload: %s", exc)
            return None
    return None


def _analysis_scores(analysis: dict[str, Any] | None) -> tuple[str, str, str]:
    eff_score = "N/A"
    qual_score = "N/A"
    fulfillment = "N/A"
    if analysis:
        e_val = analysis.get("efficiency_score")
        q_val = analysis.get("effectiveness_score")
        o_val = analysis.get("overall_score")
        if e_val is not None:
            eff_score = f"{e_val}%"
        if q_val is not None:
            qual_score = f"{q_val}%"
        if o_val is not None:
            fulfillment = f"{o_val}%"
    return eff_score, qual_score, fulfillment


def render_weekly_kr_strategic_status(
    *,
    st_module: Any,
    mode: str,
    krs_list: list[Any],
    username: str,
    calculate_kr_score_fn: Callable[..., float],
    get_score_label_fn: Callable[[float], str],
    get_score_color_band_fn: Callable[[float], str],
    analyze_node_fn: Callable[..., dict[str, Any]],
    update_key_result_fn: Callable[..., Any],
    json_loads_fn: Callable[[str], Any],
    logger: Any,
) -> bool:
    """Render weekly KR strategic status table.

    Returns True when caller should abort remaining report rendering.
    """
    if mode != "Weekly":
        return False

    st_module.markdown("---")
    st_module.subheader("Key Result Strategic Status")

    if not krs_list:
        st_module.info("No Key Results found.")
        return False

    h1, h2, h3, h4, h5, h6 = st_module.columns([2.5, 1.2, 1.2, 1.2, 1.2, 0.8])
    h1.markdown("**Key Result**")
    h2.markdown("**Status**", help="Current normalized score")
    h3.markdown("**Efficiency**", help="Completeness of work scope vs required")
    h4.markdown("**Effectiveness**", help="Quality of strategy and methods")
    h5.markdown("**Fulfillment**", help="Overall Score")
    h6.markdown("**Action**")

    st_module.markdown(
        "<hr style='margin: 5px 0; border: none; border-top: 1px solid #eee;'>",
        unsafe_allow_html=True,
    )

    for kr_item in krs_list:
        c1_kr, c2_kr, c3_kr, c4_kr, c5_kr, c6_kr = st_module.columns(
            [2.5, 1.2, 1.2, 1.2, 1.2, 0.8]
        )
        c1_kr.markdown(str(getattr(kr_item, "title", "")))

        kr_score = calculate_kr_score_fn(
            current=getattr(kr_item, "current_value", None),
            target=getattr(kr_item, "target_value", None),
            start=getattr(kr_item, "start_value", None),
            metric_type=getattr(kr_item, "metric_type", None),
        )
        score_label = get_score_label_fn(kr_score)
        band_class = get_score_color_band_fn(kr_score)
        c2_kr.markdown(
            f"<span class='atlas-attn-chip {band_class}'>{kr_score:.2f} ({score_label})</span>",
            unsafe_allow_html=True,
        )

        p_eff = c3_kr.empty()
        p_qual = c4_kr.empty()
        p_full = c5_kr.empty()
        do_update = c6_kr.button(
            "🔄",
            key=f"upd_kr_{getattr(kr_item, 'id', '')}",
            help="Update Analysis",
        )

        st_module.markdown(
            "<hr style='margin: 5px 0; border: none; border-top: 0.5px solid #f0f0f0;'>",
            unsafe_allow_html=True,
        )
        p_details = st_module.empty()

        def render_kr_state(node_kr: Any) -> None:
            analysis = _analysis_dict(
                analysis_raw=getattr(node_kr, "gemini_analysis", None),
                json_loads_fn=json_loads_fn,
                logger=logger,
            )
            eff_score, qual_score, fulfillment = _analysis_scores(analysis)
            p_eff.markdown(eff_score)
            p_qual.markdown(qual_score)
            p_full.markdown(f"**{fulfillment}**")

            with p_details.container():
                if not analysis:
                    return
                with st_module.expander("📝 Analysis Details"):
                    if analysis.get("summary"):
                        st_module.markdown(
                            f"**Executive Summary:** {analysis.get('summary')}"
                        )
                    c_d1, c_d2 = st_module.columns(2)
                    with c_d1:
                        if analysis.get("gap_analysis"):
                            st_module.markdown(
                                f"**Gap Analysis:**\n{analysis.get('gap_analysis')}"
                            )
                    with c_d2:
                        if analysis.get("quality_assessment"):
                            st_module.markdown(
                                f"**Quality Assessment:**\n{analysis.get('quality_assessment')}"
                            )

        render_kr_state(kr_item)

        if do_update:
            with st_module.spinner("Analyzing..."):
                res_kr = analyze_node_fn(
                    getattr(kr_item, "id", None),
                    "KEY_RESULT",
                    actor_username=username,
                )
                if "error" in res_kr:
                    st_module.error(str(res_kr["error"]))
                    continue
                try:
                    update_key_result_fn(
                        getattr(kr_item, "id", None),
                        gemini_analysis=res_kr,
                        actor_username=username,
                    )
                except PermissionError as exc:
                    st_module.error(str(exc))
                    return True
                kr_item.gemini_analysis = res_kr
                render_kr_state(kr_item)

    return False
