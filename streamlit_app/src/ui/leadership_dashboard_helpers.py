"""Leadership dashboard rendering helpers."""

from __future__ import annotations

import plotly.graph_objects as go

def render_leadership_dashboard_content(
    username,
    *,
    st_module,
    cached_get_all_users_fn,
    cached_get_team_members_fn,
    cached_get_leadership_metrics_fn,
    cached_get_all_tasks_by_cycle_fn,
    cycle_task_scan_limit_fn,
    utc_now_naive_fn,
    escape_html_fn,
    logger,
):
    # (Title is now in the dialog header)
    cycle_id = st_module.session_state.get("active_cycle_id")
    if not cycle_id:
        st_module.warning("Please select a cycle to view insights.")
        return

    # === REFRESH BUTTON ===
    col_refresh, col_spacer = st_module.columns([1, 5])
    with col_refresh:
        if st_module.button(
            "🔄 Refresh Data", help="Reload dashboard data", key="dash_refresh"
        ):
            # Clear session state data cache
            keys_to_clear = [
                k for k in st_module.session_state.keys() if k.startswith("okr_data_cache_")
            ]
            for k in keys_to_clear:
                del st_module.session_state[k]

            if "report_summary" in st_module.session_state:
                del st_module.session_state["report_summary"]
            st_module.rerun()

    user_role = st_module.session_state.get("user_role", "member")

    # === TEAM MEMBER FILTER (Admin/Manager only) ===
    selected_members = [username]  # Default to current user
    member_display_map = {username: st_module.session_state.get("display_name", username)}

    if user_role in ["admin", "manager"]:
        st_module.markdown("#### 👥 Team Filter")

        # Get team members based on role
        if user_role == "admin":
            all_users = cached_get_all_users_fn()
        else:
            from src.crud import get_user_by_id

            manager_id = st_module.session_state.get("user_id")
            all_users = cached_get_team_members_fn(manager_id)
            # Include self (manager) in the list
            manager_user = get_user_by_id(manager_id)
            if manager_user and manager_user not in all_users:
                all_users.insert(0, manager_user)

        # Filter active users and create options
        active_users = [u for u in all_users if u.is_active]
        member_display_map = {
            u.username: u.display_name or u.username for u in active_users
        }
        member_usernames = [u.username for u in active_users]

        if member_usernames:
            # Multi-select with all selected by default
            selected_usernames = st_module.multiselect(
                "Select members to include in dashboard",
                options=member_usernames,
                default=member_usernames,
                format_func=lambda uname: member_display_map.get(uname, uname),
                help="Filter dashboard metrics to show data for selected members only",
                key="dash_members",
            )

            selected_members = selected_usernames

            if not selected_members:
                st_module.warning("Please select at least one team member.")
                return

        st_module.markdown("---")

    # === AGGREGATE METRICS FROM SELECTED MEMBERS ===
    from src.utils.deadline_utils import get_deadline_summary, get_deadline_status

    # === FETCH AGGREGATED METRICS ===
    metrics = cached_get_leadership_metrics_fn(
        selected_members,
        cycle_id,
        actor_username=username,
    )
    if not metrics:
        st_module.error("Could not fetch metrics.")
        return
    users_map = {u.id: u for u in cached_get_all_users_fn() if u.id is not None}

    member_progress_data = metrics.get("member_progress", [])
    member_deadline_data = metrics.get("member_deadlines", [])

    # === SCORECARD ===
    st_module.markdown("#### 📈 Key Metrics")
    col1, col2, col3, col4, col5 = st_module.columns(5)

    with col1:
        st_module.metric(
            "Data Hygiene",
            f"{metrics['hygiene_pct']:.0f}%",
            help="% of KRs updated in the last 7 days",
        )
    with col2:
        st_module.metric(
            "Avg Confidence",
            f"{metrics['avg_confidence']:.1f}/10",
            delta_color="normal",
        )
    with col3:
        st_module.metric(
            "At-Risk KRs",
            metrics["at_risk_count"],
            delta="-bad" if metrics["at_risk_count"] > 0 else "off",
        )

    # Calculate aggregate deadline stats from member_deadlines
    total_overdue = sum(m["overdue"] for m in member_deadline_data)
    total_at_risk = sum(m["at_risk"] for m in member_deadline_data)

    # Aggregate deadline summary for AI coach (constructed from member_deadline_data)
    aggregate_deadline = {
        "total_with_deadline": sum(
            m.get("overdue", 0) + m.get("at_risk", 0) + m.get("on_track", 0)
            for m in member_deadline_data
        ),
        "completed": sum(m.get("completed", 0) for m in member_deadline_data),
        "on_track": sum(m.get("on_track", 0) for m in member_deadline_data),
        "at_risk": sum(m.get("at_risk", 0) for m in member_deadline_data),
        "overdue": sum(m.get("overdue", 0) for m in member_deadline_data),
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

    # === PROGRESS BY MEMBER (Only show if multiple members) ===
    if len(selected_members) > 1 and member_progress_data:
        st_module.markdown("#### 📊 Progress by Team Member")

        # Sort by progress descending
        sorted_progress = sorted(
            member_progress_data, key=lambda x: x["progress"], reverse=True
        )

        fig_progress = go.Figure()

        # Add progress bars
        fig_progress.add_trace(
            go.Bar(
                y=[m["member"] for m in sorted_progress],
                x=[m["progress"] for m in sorted_progress],
                orientation="h",
                marker=dict(
                    color=[m["progress"] for m in sorted_progress],
                    colorscale="RdYlGn",
                    cmin=0,
                    cmax=100,
                ),
                text=[
                    f"{m['progress']}% ({m['completed']}/{m['tasks']} tasks)"
                    for m in sorted_progress
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

        st_module.plotly_chart(fig_progress, key="dash_bar_progress", use_container_width=True)
        st_module.markdown("---")

    # === DEADLINE HEALTH BY MEMBER ===
    if len(selected_members) > 1 and any(
        m["overdue"] + m["at_risk"] > 0 for m in member_deadline_data
    ):
        st_module.markdown("#### 📅 Deadline Health by Member")

        # Filter to members with deadline issues
        members_with_issues = [
            m for m in member_deadline_data if m["overdue"] + m["at_risk"] > 0
        ]

        if members_with_issues:
            fig_deadline = go.Figure()

            member_names = [m["member"] for m in members_with_issues]

            fig_deadline.add_trace(
                go.Bar(
                    name="🔴 Overdue",
                    y=member_names,
                    x=[m["overdue"] for m in members_with_issues],
                    orientation="h",
                    marker_color="#E53935",
                )
            )
            fig_deadline.add_trace(
                go.Bar(
                    name="🟡 At Risk",
                    y=member_names,
                    x=[m["at_risk"] for m in members_with_issues],
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

    # === STRATEGIC ALIGNMENT MATRIX ===
    st_module.markdown("#### 📊 Strategic Alignment Matrix")

    data_heatmap = metrics["heatmap_data"]
    if data_heatmap:
        import pandas as pd

        df = pd.DataFrame(data_heatmap)

        colors = df["confidence"]

        fig = go.Figure(
            data=go.Scatter(
                x=df["efficiency"],
                y=df["effectiveness"],
                mode="markers+text",
                text=df["title"],
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
                hovertext=df.apply(
                    lambda row: (
                        f"<b>{row['title']}</b><br>Eff: {row['efficiency']}%<br>Str fit: {row['effectiveness']}%"
                    ),
                    axis=1,
                ),
                hoverinfo="text",
            )
        )

        # Quadrant Lines
        fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)

        # Quadrant Labels
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
    else:
        st_module.info(
            "Not enough AI analysis data yet. Run AI analysis on Key Results to populate this chart."
        )

    # === AT-RISK KEY RESULTS (Grouped by Member if multi-select) ===
    if metrics["at_risk"]:
        st_module.markdown("#### 🚨 At-Risk Key Results")
        for item in metrics["at_risk"]:
            st_module.error(
                f"**{item['title']}** — Reason: {item['reason']} (Conf: {item['confidence']})"
            )

    # === OVERDUE TASKS LIST ===
    # Build overdue tasks list from DB tasks for current cycle
    overdue_tasks = []
    try:
        task_scan_limit = cycle_task_scan_limit_fn()
        tasks = cached_get_all_tasks_by_cycle_fn(cycle_id, limit=task_scan_limit)
        for task in tasks:
            # Build a lightweight node dict for deadline utils
            dl = None
            if getattr(task, "deadline", None):
                # Task.deadline may be datetime or int(ms)
                dval = task.deadline
                if hasattr(dval, "timestamp"):
                    dl = int(dval.timestamp() * 1000)
                else:
                    dl = dval

            node = {
                "type": "TASK",
                "deadline": dl,
                "progress": getattr(task, "progress", 0),
                "createdAt": int(
                    getattr(task, "created_at", utc_now_naive_fn()).timestamp() * 1000
                ),
                "title": getattr(task, "title", "Untitled"),
            }
            status_code_dl, _, _ = get_deadline_status(node)
            if status_code_dl == "overdue":
                # Owner display: try to find goal.owner via relationships
                owner_disp = "Unknown"
                try:
                    if (
                        task.key_result
                        and task.key_result.objective
                        and task.key_result.objective.goal
                    ):
                        goal_owner_id = task.key_result.objective.goal.owner_id
                        if goal_owner_id and goal_owner_id in users_map:
                            user_obj = users_map[goal_owner_id]
                            owner_disp = user_obj.display_name or user_obj.username
                except Exception as exc:
                    logger.debug("Failed to resolve overdue task owner display: %s", exc)
                    owner_disp = "Unknown"

                overdue_tasks.append(
                    {
                        "title": node.get("title", "Untitled"),
                        "owner": owner_disp,
                        "progress": node.get("progress", 0),
                    }
                )
    except Exception as exc:
        logger.warning("Failed while building overdue task list: %s", exc)
        overdue_tasks = []

    if overdue_tasks:
        st_module.markdown("#### 🔴 Overdue Tasks")
        if len(tasks) >= task_scan_limit:
            st_module.caption(
                f"Showing results from first {task_scan_limit} tasks in this cycle. "
                "Increase OKR_UI_CYCLE_TASK_SCAN_LIMIT for deeper scans."
            )
        limit_overdue = st_module.number_input(
            "Max overdue tasks to show", min_value=5, max_value=100, value=10, step=5
        )
        for task in overdue_tasks[:limit_overdue]:
            st_module.error(
                f"**{task['title']}** — Owner: {task['owner']} ({task['progress']}% complete)"
            )
        if len(overdue_tasks) > limit_overdue:
            st_module.caption(
                f"...and {len(overdue_tasks) - limit_overdue} more overdue tasks"
            )

    # === AI TEAM COACH (Admin/Manager only) ===
    if user_role in ["admin", "manager"]:
        st_module.markdown("---")
        st_module.markdown("#### 🧠 AI Team Coach")
        st_module.caption("Get strategic coaching tips based on your team's performance data")

        # Prepare team data for AI
        team_coaching_data = {
            "members": member_progress_data,
            "total_with_deadline": aggregate_deadline.get("total_with_deadline", 0),
            "completed": aggregate_deadline.get("completed", 0),
            "on_track": aggregate_deadline.get("on_track", 0),
            "at_risk": aggregate_deadline.get("at_risk", 0),
            "overdue": aggregate_deadline.get("overdue", 0),
            "total_krs": metrics.get("total_krs", 0),
            "at_risk_krs": len(metrics.get("at_risk", [])),
            "avg_confidence": metrics.get("avg_confidence", 0),
            "hygiene_pct": metrics.get("hygiene_pct", 0),
            "progress_distribution": member_progress_data,
        }

        col_coach_btn, col_coach_spacer = st_module.columns([1, 3])
        with col_coach_btn:
            run_coach = st_module.button(
                "✨ Get Coaching Tips",
                type="primary",
                use_container_width=True,
                key="dash_coach_btn",
            )

        if run_coach:
            from src.services.ai_service import analyze_team_health

            with st_module.spinner("🧠 AI Coach is analyzing your team..."):
                result = analyze_team_health(team_coaching_data)

            if "error" in result:
                st_module.error(f"Coaching failed: {result['error']}")
            else:
                coaching = result.get("coaching", {})

                # Store in session for persistence
                st_module.session_state["last_coaching"] = coaching

        # Display coaching results (if available)
        coaching = st_module.session_state.get("last_coaching")
        if coaching:
            # Health Score Header
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

            # Color based on grade
            grade_colors = {
                "A": "#4CAF50",
                "B": "#8BC34A",
                "C": "#FFC107",
                "D": "#FF9800",
                "F": "#F44336",
            }
            grade_display = grade if grade in grade_colors else "?"
            grade_color = grade_colors.get(grade_display, "#9E9E9E")

            # Score Card
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

            # Dimension Scores
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

                # Display as columns with progress bars
                cols = st_module.columns(5)
                for i, (key, label) in enumerate(dim_labels.items()):
                    dim = dimensions.get(key, {})
                    score_val = dim.get("score", 0)
                    status_str = dim.get("status", "")

                    with cols[i]:
                        st_module.metric(label.split(" ")[0], f"{score_val}%")
                        if "🟢" in status_str:
                            st_module.success(status_str, icon="✅")
                        elif "🔴" in status_str:
                            st_module.error(status_str, icon="🚨")
                        else:
                            st_module.warning(status_str, icon="⚠️")

                # Expandable insights per dimension
                with st_module.expander("💡 Detailed Insights & Actions", expanded=False):
                    for key, label in dim_labels.items():
                        dim = dimensions.get(key, {})
                        st_module.markdown(f"**{label}**")
                        st_module.info(f"📌 {dim.get('insight', 'N/A')}")
                        st_module.success(f"✅ Action: {dim.get('action', 'N/A')}")
                        st_module.markdown("---")

            # Top Priorities
            priorities = coaching.get("top_priorities", [])
            if priorities:
                st_module.markdown("##### 🎯 Top Priorities This Week")
                for i, p in enumerate(priorities, 1):
                    st_module.markdown(f"**{i}.** {p}")

            # Quick Wins
            quick_wins = coaching.get("quick_wins", [])
            if quick_wins:
                st_module.markdown("##### ⚡ Quick Wins")
                for win in quick_wins:
                    st_module.success(f"💡 {win}")

            # Watch Out
            watch_out = coaching.get("watch_out")
            if watch_out:
                st_module.markdown("##### ⚠️ Risk Alert")
                st_module.warning(f"🔔 {watch_out}")


