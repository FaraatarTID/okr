"""AI team coach rendering helpers for leadership dashboard."""

from __future__ import annotations

from typing import Any, Callable


def render_ai_team_coach(
    *,
    st_module: Any,
    user_role: str,
    member_progress_data: list[dict[str, Any]],
    aggregate_deadline: dict[str, int],
    metrics: dict[str, Any],
    analyze_team_health_fn: Callable[[dict[str, Any]], dict[str, Any]],
    escape_html_fn: Callable[[str], str],
    logger: Any,
) -> None:
    """Render AI team coach section for admin/manager roles."""
    if user_role not in ["admin", "manager"]:
        return

    st_module.markdown("---")
    st_module.markdown("#### 🧠 AI Team Coach")
    st_module.caption(
        "Get strategic coaching tips based on your team's performance data"
    )

    team_coaching_data = {
        "members": member_progress_data,
        "total_with_deadline": aggregate_deadline.get("total_with_deadline", 0),
        "completed": aggregate_deadline.get("completed", 0),
        "on_track": aggregate_deadline.get("on_track", 0),
        "at_risk": aggregate_deadline.get("at_risk", 0),
        "overdue": aggregate_deadline.get("overdue", 0),
        "total_krs": int(metrics.get("total_krs", 0) or 0),
        "at_risk_krs": len(metrics.get("at_risk", [])),
        "avg_confidence": float(metrics.get("avg_confidence", 0) or 0),
        "hygiene_pct": float(metrics.get("hygiene_pct", 0) or 0),
        "progress_distribution": member_progress_data,
    }

    col_coach_btn, _col_coach_spacer = st_module.columns([1, 3])
    with col_coach_btn:
        run_coach = st_module.button(
            "✨ Get Coaching Tips",
            type="primary",
            use_container_width=True,
            key="dash_coach_btn",
        )

    if run_coach:
        with st_module.spinner("🧠 AI Coach is analyzing your team..."):
            result = analyze_team_health_fn(team_coaching_data)

        if "error" in result:
            st_module.error(f"Coaching failed: {result['error']}")
        else:
            st_module.session_state["last_coaching"] = result.get("coaching", {})

    coaching = st_module.session_state.get("last_coaching")
    if not coaching:
        return

    try:
        health_score = int(float(coaching.get("overall_health_score", 0)))
    except Exception as exc:
        logger.debug(
            "Failed to parse coaching overall_health_score '%s': %s",
            coaching.get("overall_health_score"),
            exc,
        )
        health_score = 0
    grade = str(coaching.get("health_grade", "?"))[:1].upper() or "?"
    headline = escape_html_fn(str(coaching.get("headline", "")))

    grade_colors = {
        "A": "#4CAF50",
        "B": "#8BC34A",
        "C": "#FFC107",
        "D": "#FF9800",
        "F": "#F44336",
    }
    grade_display = grade if grade in grade_colors else "?"
    grade_color = grade_colors.get(grade_display, "#9E9E9E")

    st_module.markdown(
        f"""
            <div style="background: linear-gradient(135deg, {grade_color}22, {grade_color}11);
                        border-left: 4px solid {grade_color};
                        padding: 20px;
                        border-radius: 8px;
                        margin: 10px 0;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="text-align: center;">
                        <div style="font-size: 48px; font-weight: bold; color: {grade_color};">{grade_display}</div>
                        <div style="font-size: 14px; color: #666;">Grade</div>
                    </div>
                    <div style="flex: 1;">
                        <div style="font-size: 24px; font-weight: 500; margin-bottom: 8px;">Team Health: {health_score}%</div>
                        <div style="font-size: 16px; color: #555;">{headline}</div>
                    </div>
                </div>
            </div>
            """,
        unsafe_allow_html=True,
    )

    dimensions = coaching.get("dimensions", {})
    if dimensions:
        st_module.markdown("##### 📊 Performance Dimensions")

        dim_labels = {
            "productivity": "🚀 Productivity",
            "deadline_discipline": "⏰ Deadline Discipline",
            "strategic_alignment": "🎯 Strategic Alignment",
            "workload_balance": "⚖️ Workload Balance",
            "momentum": "📈 Momentum",
        }
        cols = st_module.columns(5)
        for index, (key, label) in enumerate(dim_labels.items()):
            dimension = dimensions.get(key, {})
            score_value = dimension.get("score", 0)
            status_text = str(dimension.get("status", ""))
            with cols[index]:
                st_module.metric(label.split(" ")[0], f"{score_value}%")
                if "🟢" in status_text:
                    st_module.success(status_text, icon="✅")
                elif "🔴" in status_text:
                    st_module.error(status_text, icon="🚨")
                else:
                    st_module.warning(status_text, icon="⚠️")

        with st_module.expander("💡 Detailed Insights & Actions", expanded=False):
            for key, label in dim_labels.items():
                dimension = dimensions.get(key, {})
                st_module.markdown(f"**{label}**")
                st_module.info(f"📌 {dimension.get('insight', 'N/A')}")
                st_module.success(f"✅ Action: {dimension.get('action', 'N/A')}")
                st_module.markdown("---")

    priorities = coaching.get("top_priorities", [])
    if priorities:
        st_module.markdown("##### 🎯 Top Priorities This Week")
        for index, item in enumerate(priorities, 1):
            st_module.markdown(f"**{index}.** {item}")

    quick_wins = coaching.get("quick_wins", [])
    if quick_wins:
        st_module.markdown("##### ⚡ Quick Wins")
        for win in quick_wins:
            st_module.success(f"💡 {win}")

    watch_out = coaching.get("watch_out")
    if watch_out:
        st_module.markdown("##### ⚠️ Risk Alert")
        st_module.warning(f"🔔 {watch_out}")
