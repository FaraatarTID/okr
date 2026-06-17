"""Chart and metric rendering helpers for leadership dashboard."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


def render_scorecard_metrics(
    *,
    st_module: Any,
    metrics: dict[str, Any],
    member_deadline_data: list[dict[str, Any]],
) -> dict[str, int]:
    """Render dashboard KPI scorecards and return aggregated deadline totals."""
    st_module.markdown("#### 📈 Key Metrics")
    col1, col2, col3, col4, col5 = st_module.columns(5)

    with col1:
        st_module.metric(
            "Data Hygiene",
            f"{float(metrics.get('hygiene_pct', 0)):.0f}%",
            help="% of KRs updated in the last 7 days",
        )
    with col2:
        st_module.metric(
            "Avg Confidence",
            f"{float(metrics.get('avg_confidence', 0)):.1f}/10",
            delta_color="normal",
        )
    with col3:
        at_risk_count = int(metrics.get("at_risk_count", 0) or 0)
        st_module.metric(
            "At-Risk KRs",
            at_risk_count,
            delta="-bad" if at_risk_count > 0 else "off",
        )

    total_overdue = sum(
        int(item.get("overdue", 0) or 0) for item in member_deadline_data
    )
    total_at_risk = sum(
        int(item.get("at_risk", 0) or 0) for item in member_deadline_data
    )

    aggregate_deadline = {
        "total_with_deadline": sum(
            int(item.get("overdue", 0) or 0)
            + int(item.get("at_risk", 0) or 0)
            + int(item.get("on_track", 0) or 0)
            for item in member_deadline_data
        ),
        "completed": sum(
            int(item.get("completed", 0) or 0) for item in member_deadline_data
        ),
        "on_track": sum(
            int(item.get("on_track", 0) or 0) for item in member_deadline_data
        ),
        "at_risk": total_at_risk,
        "overdue": total_overdue,
    }

    with col4:
        st_module.metric(
            "🔴 Overdue Tasks",
            total_overdue,
            delta="-bad" if total_overdue > 0 else "off",
            help="Tasks past deadline with < 100% progress",
        )
    with col5:
        st_module.metric(
            "🟡 At Risk Tasks",
            total_at_risk,
            delta="-normal" if total_at_risk > 0 else "off",
            help="Tasks behind expected progress pace",
        )

    st_module.markdown("---")
    return aggregate_deadline


def render_progress_by_member_chart(
    *,
    st_module: Any,
    selected_members: list[str],
    member_progress_data: list[dict[str, Any]],
) -> None:
    """Render member progress bar chart when comparing multiple members."""
    if len(selected_members) <= 1 or not member_progress_data:
        return

    st_module.markdown("#### 📊 Progress by Team Member")
    sorted_progress = sorted(
        member_progress_data,
        key=lambda item: float(item.get("progress", 0) or 0),
        reverse=True,
    )

    fig_progress = go.Figure()
    fig_progress.add_trace(
        go.Bar(
            y=[str(item.get("member", "")) for item in sorted_progress],
            x=[float(item.get("progress", 0) or 0) for item in sorted_progress],
            orientation="h",
            marker=dict(
                color=[float(item.get("progress", 0) or 0) for item in sorted_progress],
                colorscale="RdYlGn",
                cmin=0,
                cmax=100,
            ),
            text=[
                f"{item.get('progress', 0)}% ({item.get('completed', 0)}/{item.get('tasks', 0)} tasks)"
                for item in sorted_progress
            ],
            textposition="inside",
            hovertemplate="<b>%{y}</b><br>Progress: %{x}%<extra></extra>",
        )
    )
    fig_progress.update_layout(
        xaxis_title="Average Task Progress %",
        xaxis=dict(range=[0, 105]),
        height=max(200, len(sorted_progress) * 40),
        showlegend=False,
        template="simple_white",
    )
    st_module.plotly_chart(
        fig_progress, key="dash_bar_progress", use_container_width=True
    )
    st_module.markdown("---")


def render_deadline_health_chart(
    *,
    st_module: Any,
    selected_members: list[str],
    member_deadline_data: list[dict[str, Any]],
) -> None:
    """Render stacked overdue/at-risk chart by member."""
    has_any_issue = any(
        int(item.get("overdue", 0) or 0) + int(item.get("at_risk", 0) or 0) > 0
        for item in member_deadline_data
    )
    if len(selected_members) <= 1 or not has_any_issue:
        return

    st_module.markdown("#### 📅 Deadline Health by Member")
    members_with_issues = [
        item
        for item in member_deadline_data
        if int(item.get("overdue", 0) or 0) + int(item.get("at_risk", 0) or 0) > 0
    ]
    if not members_with_issues:
        st_module.markdown("---")
        return

    fig_deadline = go.Figure()
    member_names = [str(item.get("member", "")) for item in members_with_issues]
    fig_deadline.add_trace(
        go.Bar(
            name="🔴 Overdue",
            y=member_names,
            x=[int(item.get("overdue", 0) or 0) for item in members_with_issues],
            orientation="h",
            marker_color="#E53935",
        )
    )
    fig_deadline.add_trace(
        go.Bar(
            name="🟡 At Risk",
            y=member_names,
            x=[int(item.get("at_risk", 0) or 0) for item in members_with_issues],
            orientation="h",
            marker_color="#FFA726",
        )
    )
    fig_deadline.update_layout(
        barmode="stack",
        xaxis_title="Number of Tasks",
        height=max(200, len(members_with_issues) * 50),
        template="simple_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st_module.plotly_chart(
        fig_deadline, key="dash_bar_deadline", use_container_width=True
    )
    st_module.markdown("---")


def render_strategic_alignment_matrix(
    *,
    st_module: Any,
    heatmap_data: list[dict[str, Any]],
) -> None:
    """Render strategic alignment scatter matrix."""
    st_module.markdown("#### 📊 Strategic Alignment Matrix")
    if not heatmap_data:
        st_module.info(
            "Not enough AI analysis data yet. Run AI analysis on Key Results to populate this chart."
        )
        return

    import pandas as pd

    dataframe = pd.DataFrame(heatmap_data)
    colors = dataframe["confidence"]

    fig = go.Figure(
        data=go.Scatter(
            x=dataframe["efficiency"],
            y=dataframe["effectiveness"],
            mode="markers+text",
            text=dataframe["title"],
            textposition="top center",
            marker=dict(
                size=14,
                color=colors,
                colorscale="RdYlGn",
                cmin=0,
                cmax=10,
                showscale=True,
                colorbar=dict(title="Confidence"),
                line=dict(color="black", width=1),
            ),
            hovertext=dataframe.apply(
                lambda row: (
                    f"<b>{row['title']}</b><br>Eff: {row['efficiency']}%<br>Str fit: {row['effectiveness']}%"
                ),
                axis=1,
            ),
            hoverinfo="text",
        )
    )
    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_annotation(
        x=90,
        y=90,
        text="🌟 High Performers",
        showarrow=False,
        font=dict(color="green"),
    )
    fig.add_annotation(
        x=90, y=10, text="⚠️ Busy Work", showarrow=False, font=dict(color="orange")
    )
    fig.add_annotation(
        x=10, y=90, text="🤔 Strategy Gap", showarrow=False, font=dict(color="blue")
    )
    fig.add_annotation(
        x=10, y=10, text="❌ Disconnected", showarrow=False, font=dict(color="red")
    )
    fig.update_layout(
        xaxis_title="Efficiency (Execution Quality)",
        yaxis_title="Effectiveness (Strategy Fit)",
        xaxis=dict(range=[0, 105]),
        yaxis=dict(range=[0, 105]),
        height=500,
        template="simple_white",
    )
    st_module.plotly_chart(fig, key="dash_scatter_strategic", use_container_width=True)


def render_at_risk_key_results(
    *,
    st_module: Any,
    at_risk_items: list[dict[str, Any]],
) -> None:
    """Render at-risk KR list."""
    if not at_risk_items:
        return

    st_module.markdown("#### 🚨 At-Risk Key Results")
    for item in at_risk_items:
        st_module.error(
            f"**{item.get('title', 'Untitled')}** — Reason: {item.get('reason', 'N/A')} (Conf: {item.get('confidence', 'N/A')})"
        )


def render_overdue_tasks(
    *,
    st_module: Any,
    overdue_tasks: list[dict[str, Any]],
    scanned_task_count: int,
    task_scan_limit: int,
) -> None:
    """Render overdue tasks section with local display cap controls."""
    if not overdue_tasks:
        return

    st_module.markdown("#### 🔴 Overdue Tasks")
    if scanned_task_count >= task_scan_limit:
        st_module.caption(
            f"Showing results from first {task_scan_limit} tasks in this cycle. "
            "Increase OKR_UI_CYCLE_TASK_SCAN_LIMIT for deeper scans."
        )

    limit_overdue = int(
        st_module.number_input(
            "Max overdue tasks to show", min_value=5, max_value=100, value=10, step=5
        )
    )
    for task in overdue_tasks[:limit_overdue]:
        st_module.error(
            f"**{task['title']}** — Owner: {task['owner']} ({task['progress']}% complete)"
        )
    if len(overdue_tasks) > limit_overdue:
        st_module.caption(
            f"...and {len(overdue_tasks) - limit_overdue} more overdue tasks"
        )
