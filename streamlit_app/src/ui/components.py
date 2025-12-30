import streamlit as st
import time
import os
import sys
from datetime import datetime
import plotly.graph_objects as go
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config

# Import UI constants
from src.ui.styles import TYPE_ICONS, TYPE_COLORS, CHILD_TYPE_MAP, TYPES

def format_time(minutes):
    """Simple formatter for minutes -> HH:MM"""
    if minutes < 0: minutes = 0
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"

def build_graph_from_node(node_id, data):
    """
    Recursively build a graph (nodes and edges) from a starting node.
    Returns (list of Node, list of Edge) for streamlit-agraph.
    """
    nodes_list = []
    edges_list = []
    visited = set()

    def traverse(nid, parent_nid=None):
        if nid in visited: return
        visited.add(nid)
        
        node = data["nodes"].get(nid)
        if not node: return
        
        ntype = node.get("type", "GOAL")
        color = TYPE_COLORS.get(ntype, "#757575")
        icon = TYPE_ICONS.get(ntype, "")
        title = node.get("title", "Untitled")
        
        # Add Node
        nodes_list.append(Node(
            id=nid,
            label=f"{icon} {title}",
            size=25, # Fixed size for graph view
            color=color
        ))
        
        # Add Edge
        if parent_nid:
            edges_list.append(Edge(
                source=parent_nid,
                target=nid,
                label="",
                color="#CCCCCC"
            ))
            
        for child_id in node.get("children", []):
            traverse(child_id, nid)
    
    traverse(node_id)
    return nodes_list, edges_list

def navigate_to(node_id):
    """Push node to stack."""
    if "nav_stack" in st.session_state:
        st.session_state.nav_stack.append(node_id)
        st.rerun()

def navigate_back_to(index):
    """Pop stack to specific index."""
    if "nav_stack" in st.session_state:
        st.session_state.nav_stack = st.session_state.nav_stack[:index+1]
        st.rerun()

def render_breadcrumbs(data):
    """Render clickable breadcrumbs using pills."""
    stack = st.session_state.nav_stack
    
    options = ["HOME"] + stack
    
    def get_label(opt):
        if opt == "HOME":
           return "🏠 Home"
        node = data["nodes"].get(opt)
        if not node: return "Unknown"
        
        # User wants "Type: Title"
        title = node.get("title", "Untitled")
        ntype = node.get("type", "").replace('_',' ').title()
        return f"{ntype}: {title}"
        
    current_selection = stack[-1] if stack else "HOME"
    
    selected = st.pills(
        "Navigation",
        options=options,
        selection_mode="single",
        default=current_selection,
        format_func=get_label,
        key="nav_pills"
    )
    
    if selected != current_selection:
        if selected == "HOME":
            st.session_state.nav_stack = []
            st.rerun()
        else:
            try:
                idx = stack.index(selected)
                navigate_back_to(idx)
            except ValueError:
                pass

def get_ancestor_objective(node_id, nodes):
    """
    Traverse up the hierarchy to find the Objective for a given node.
    Returns the title of the Objective, or "Other / No Objective".
    """
    current_id = node_id
    while current_id:
        node = nodes.get(current_id)
        if not node:
            break
        
        if node.get("type") == "OBJECTIVE":
            return node.get("title", "Untitled Objective")
            
        current_id = node.get("parentId")
    
    return "Other / No Objective"

def get_ancestor_key_result(node_id, nodes):
    """
    Traverse up the hierarchy to find the Key Result for a given node.
    Returns the title of the Key Result, or "-".
    """
    current_id = node_id
    while current_id:
        node = nodes.get(current_id)
        if not node: break
        
        if node.get("type") == "KEY_RESULT":
            return node.get("title", "Untitled KR")
        
        current_id = node.get("parentId")
    
    return "-"

def render_timer_content(node_id, data, username):
    from utils.storage import stop_timer
    
    node = data["nodes"].get(node_id)
    if not node:
        st.error("Task not found")
        return
        
    st.markdown(f"<div class='timer-task-title'>{node.get('title')}</div>", unsafe_allow_html=True)
    st.markdown("<div class='timer-subtext'>Focus on this task and record your flow.</div>", unsafe_allow_html=True)
    
    placeholder = st.empty()
    
    # Action buttons
    c1, c2, c3 = st.columns([1,1,1])
    
    # We use a loop for the "live" feel
    # But since this is a fragment/dialog, it's easier to use session state
    start_ts = node.get("timerStartedAt")
    
    if start_ts:
        elapsed_sec = int(time.time() - start_ts / 1000)
        h = elapsed_sec // 3600
        m = (elapsed_sec % 3600) // 60
        s = elapsed_sec % 60
        
        placeholder.markdown(f"<div class='timer-display'>{h:02d}:{m:02d}:{s:02d}</div>", unsafe_allow_html=True)
        
        summary = st.text_input("What did you work on?", placeholder="e.g. Drafted initial outline...", key=f"timer_sum_{node_id}")
        
        if c2.button("✋ Stop & Log", type="primary", use_container_width=True):
            stop_timer(data, node_id, username, summary=summary)
            if "active_timer_node_id" in st.session_state:
                del st.session_state.active_timer_node_id
            st.rerun()
            
        # Refresh every few seconds
        time.sleep(1)
        st.rerun()
    else:
        placeholder.markdown("<div class='timer-display'>00:00:00</div>", unsafe_allow_html=True)
        st.warning("Timer is not running.")
        if c2.button("Close", use_container_width=True):
             if "active_timer_node_id" in st.session_state:
                del st.session_state.active_timer_node_id
             st.rerun()

def render_leadership_dashboard_content(username):
    # (Title is now in the dialog header)
    from utils.storage import load_data
    from src.crud import get_leadership_metrics
    
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle to view insights.")
        return
    
    # === REFRESH BUTTON ===
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refresh Data", help="Clear cache and reload all data", key="dash_refresh"):
            from utils.storage import _fetch_from_source, load_all_data
            _fetch_from_source.clear()
            load_all_data.clear()
            
            # Clear session state data cache
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith("okr_data_cache_")]
            for k in keys_to_clear:
                del st.session_state[k]
                
            st.rerun()
    
    user_role = st.session_state.get("user_role", "member")
    
    # === TEAM MEMBER FILTER (Admin/Manager only) ===
    selected_members = [username]  # Default to current user
    member_display_map = {username: st.session_state.get("display_name", username)}
    
    if user_role in ["admin", "manager"]:
        st.markdown("#### 👥 Team Filter")
        
        # Get team members based on role
        if user_role == "admin":
            from src.crud import get_all_users
            all_users = get_all_users()
        else:
            from src.crud import get_team_members, get_user_by_id
            manager_id = st.session_state.get("user_id")
            all_users = get_team_members(manager_id)
            # Include self (manager) in the list
            manager_user = get_user_by_id(manager_id)
            if manager_user and manager_user not in all_users:
                all_users.insert(0, manager_user)
        
        # Filter active users and create options
        active_users = [u for u in all_users if u.is_active]
        member_options = {u.display_name or u.username: u.username for u in active_users}
        member_display_map = {u.username: u.display_name or u.username for u in active_users}
        
        if member_options:
            # Multi-select with all selected by default
            selected_names = st.multiselect(
                "Select members to include in dashboard",
                options=list(member_options.keys()),
                default=list(member_options.keys()),
                help="Filter dashboard metrics to show data for selected members only",
                key="dash_members"
            )
            
            selected_members = [member_options[name] for name in selected_names]
            
            if not selected_members:
                st.warning("Please select at least one team member.")
                return
        
        st.markdown("---")
    
    # === AGGREGATE METRICS FROM SELECTED MEMBERS ===
    from utils.deadline_utils import get_deadline_summary, get_deadline_status
    
    # Aggregate data from all selected members
    all_nodes = {}
    member_progress_data = []
    member_deadline_data = []
    
    for member_username in selected_members:
        member_data = load_data(member_username)
        member_nodes = member_data.get("nodes", {})
        
        # Merge nodes (with member tagging)
        for nid, node in member_nodes.items():
            node["_owner"] = member_username
            node["_owner_display"] = member_display_map.get(member_username, member_username)
            all_nodes[nid] = node
        
        # Calculate member-level stats
        total_progress = 0
        task_count = 0
        completed_count = 0
        
        deadline_stats = get_deadline_summary(member_nodes)
        
        for nid, node in member_nodes.items():
            if node.get("type") == "TASK":
                task_count += 1
                progress = node.get("progress", 0)
                total_progress += progress
                if progress >= 100:
                    completed_count += 1
        
        avg_progress = int(total_progress / task_count) if task_count > 0 else 0
        display_name = member_display_map.get(member_username, member_username)
        
        member_progress_data.append({
            "member": display_name,
            "username": member_username,
            "progress": avg_progress,
            "tasks": task_count,
            "completed": completed_count
        })
        
        member_deadline_data.append({
            "member": display_name,
            "username": member_username,
            "overdue": deadline_stats.get("overdue", 0),
            "at_risk": deadline_stats.get("at_risk", 0),
            "on_track": deadline_stats.get("on_track", 0),
            "completed": deadline_stats.get("completed", 0)
        })
    
    # Get aggregate deadline stats
    aggregate_deadline = get_deadline_summary(all_nodes)
    
    # Get leadership metrics for selective members
    metrics = get_leadership_metrics(selected_members, cycle_id)
    if not metrics:
        metrics = {"hygiene_pct": 0, "avg_confidence": 0, "at_risk": [], "heatmap_data": [], "total_krs": 0}
    
    # === SCORECARD ===
    st.markdown("#### 📈 Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Data Hygiene", 
            f"{metrics['hygiene_pct']:.0f}%", 
            help="% of KRs updated in the last 7 days"
        )
    with col2:
        st.metric(
            "Avg Confidence", 
            f"{metrics['avg_confidence']:.1f}/10",
            delta_color="normal"
        )
    with col3:
        st.metric(
            "At-Risk KRs", 
            len(metrics["at_risk"]),
            delta="-bad" if metrics["at_risk"] else "off"
        )
    with col4:
        st.metric(
            "🔴 Overdue Tasks",
            aggregate_deadline.get("overdue", 0),
            delta="-bad" if aggregate_deadline.get("overdue", 0) > 0 else "off",
            help="Tasks past deadline with < 100% progress"
        )
    with col5:
        st.metric(
            "🟡 At Risk Tasks",
            aggregate_deadline.get("at_risk", 0),
            delta="-normal" if aggregate_deadline.get("at_risk", 0) > 0 else "off",
            help="Tasks behind expected progress pace"
        )
    
    st.markdown("---")
    
    # === PROGRESS BY MEMBER (Only show if multiple members) ===
    if len(selected_members) > 1 and member_progress_data:
        st.markdown("#### 📊 Progress by Team Member")
        
        # Sort by progress descending
        sorted_progress = sorted(member_progress_data, key=lambda x: x["progress"], reverse=True)
        
        fig_progress = go.Figure()
        
        # Add progress bars
        fig_progress.add_trace(go.Bar(
            y=[m["member"] for m in sorted_progress],
            x=[m["progress"] for m in sorted_progress],
            orientation='h',
            marker=dict(
                color=[m["progress"] for m in sorted_progress],
                colorscale='RdYlGn',
                cmin=0,
                cmax=100
            ),
            text=[f"{m['progress']}% ({m['completed']}/{m['tasks']} tasks)" for m in sorted_progress],
            textposition='inside',
            hovertemplate="<b>%{y}</b><br>Progress: %{x}%<extra></extra>"
        ))
        
        fig_progress.update_layout(
            xaxis_title="Average Task Progress %",
            xaxis=dict(range=[0, 105]),
            height=max(200, len(sorted_progress) * 40),
            showlegend=False,
            template="simple_white"
        )
        
        st.plotly_chart(fig_progress, key="dash_bar_progress", use_container_width=True)
        st.markdown("---")
    
    # === DEADLINE HEALTH BY MEMBER ===
    if len(selected_members) > 1 and any(m["overdue"] + m["at_risk"] > 0 for m in member_deadline_data):
        st.markdown("#### 📅 Deadline Health by Member")
        
        # Filter to members with deadline issues
        members_with_issues = [m for m in member_deadline_data if m["overdue"] + m["at_risk"] > 0]
        
        if members_with_issues:
            fig_deadline = go.Figure()
            
            member_names = [m["member"] for m in members_with_issues]
            
            fig_deadline.add_trace(go.Bar(
                name="🔴 Overdue",
                y=member_names,
                x=[m["overdue"] for m in members_with_issues],
                orientation='h',
                marker_color='#E53935'
            ))
            fig_deadline.add_trace(go.Bar(
                name="🟡 At Risk",
                y=member_names,
                x=[m["at_risk"] for m in members_with_issues],
                orientation='h',
                marker_color='#FFA726'
            ))
            
            fig_deadline.update_layout(
                barmode='stack',
                xaxis_title="Number of Tasks",
                height=max(200, len(members_with_issues) * 50),
                template="simple_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            
            st.plotly_chart(fig_deadline, key="dash_bar_deadline", use_container_width=True)
        st.markdown("---")
    
    # === STRATEGIC ALIGNMENT MATRIX ===
    st.markdown("#### 📊 Strategic Alignment Matrix")
    
    data_heatmap = metrics["heatmap_data"]
    if data_heatmap:
        df = pd.DataFrame(data_heatmap)
        
        colors = df["confidence"]
        
        fig = go.Figure(data=go.Scatter(
            x=df["efficiency"],
            y=df["effectiveness"],
            mode='markers+text',
            text=df["title"],
            textposition="top center",
            marker=dict(
                size=14,
                color=colors,
                colorscale='RdYlGn',
                cmin=0,
                cmax=10,
                showscale=True,
                colorbar=dict(title="Confidence"),
                line=dict(color='black', width=1)
            ),
            hovertext=df.apply(lambda row: f"<b>{row['title']}</b><br>Eff: {row['efficiency']}%<br>Str fit: {row['effectiveness']}%", axis=1),
            hoverinfo="text"
        ))
        
        # Quadrant Lines
        fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=50, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Quadrant Labels
        fig.add_annotation(x=90, y=90, text="🌟 High Performers", showarrow=False, font=dict(color="green"))
        fig.add_annotation(x=90, y=10, text="⚠️ Busy Work", showarrow=False, font=dict(color="orange"))
        fig.add_annotation(x=10, y=90, text="🤔 Strategy Gap", showarrow=False, font=dict(color="blue"))
        fig.add_annotation(x=10, y=10, text="❌ Disconnected", showarrow=False, font=dict(color="red"))
 
        fig.update_layout(
            xaxis_title="Efficiency (Execution Quality)",
            yaxis_title="Effectiveness (Strategy Fit)",
            xaxis=dict(range=[0, 105]),
            yaxis=dict(range=[0, 105]),
            height=500,
            template="simple_white"
        )
        
        st.plotly_chart(fig, key="dash_scatter_strategic", use_container_width=True)
    else:
        st.info("Not enough AI analysis data yet. Run AI analysis on Key Results to populate this chart.")
 
    # === AT-RISK KEY RESULTS (Grouped by Member if multi-select) ===
    if metrics["at_risk"]:
        st.markdown("#### 🚨 At-Risk Key Results")
        for item in metrics["at_risk"]:
            st.error(f"**{item['title']}** — Reason: {item['reason']} (Conf: {item['confidence']})")
    
    # === OVERDUE TASKS LIST ===
    overdue_tasks = []
    for nid, node in all_nodes.items():
        if node.get("type") == "TASK" and node.get("deadline"):
            status_code_dl, _, _ = get_deadline_status(node)
            if status_code_dl == "overdue":
                overdue_tasks.append({
                    "title": node.get("title", "Untitled"),
                    "owner": node.get("_owner_display", "Unknown"),
                    "progress": node.get("progress", 0)
                })
    
    if overdue_tasks:
        st.markdown("#### 🔴 Overdue Tasks")
        for task in overdue_tasks[:10]:  # Limit to 10
            st.error(f"**{task['title']}** — Owner: {task['owner']} ({task['progress']}% complete)")
        if len(overdue_tasks) > 10:
            st.caption(f"...and {len(overdue_tasks) - 10} more overdue tasks")
 
    # === AI TEAM COACH (Admin/Manager only) ===
    if user_role in ["admin", "manager"]:
        st.markdown("---")
        st.markdown("#### 🧠 AI Team Coach")
        st.caption("Get strategic coaching tips based on your team's performance data")
        
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
            "progress_distribution": member_progress_data
        }
        
        col_coach_btn, col_coach_spacer = st.columns([1, 3])
        with col_coach_btn:
            run_coach = st.button("✨ Get Coaching Tips", type="primary", use_container_width=True, key="dash_coach_btn")
        
        if run_coach:
            from src.services.ai_service import analyze_team_health
            
            with st.spinner("🧠 AI Coach is analyzing your team..."):
                result = analyze_team_health(team_coaching_data)
            
            if "error" in result:
                st.error(f"Coaching failed: {result['error']}")
            else:
                coaching = result.get("coaching", {})
                
                # Store in session for persistence
                st.session_state["last_coaching"] = coaching
        
        # Display coaching results (if available)
        coaching = st.session_state.get("last_coaching")
        if coaching:
            # Health Score Header
            health_score = coaching.get("overall_health_score", 0)
            grade = coaching.get("health_grade", "?")
            headline = coaching.get("headline", "")
            
            # Color based on grade
            grade_colors = {"A": "#4CAF50", "B": "#8BC34A", "C": "#FFC107", "D": "#FF9800", "F": "#F44336"}
            grade_color = grade_colors.get(grade, "#9E9E9E")
            
            # Score Card
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {grade_color}22, {grade_color}11); 
                        border-left: 4px solid {grade_color}; 
                        padding: 20px; 
                        border-radius: 8px; 
                        margin: 10px 0;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="text-align: center;">
                        <div style="font-size: 48px; font-weight: bold; color: {grade_color};">{grade}</div>
                        <div style="font-size: 14px; color: #666;">Grade</div>
                    </div>
                    <div style="flex: 1;">
                        <div style="font-size: 24px; font-weight: 500; margin-bottom: 8px;">Team Health: {health_score}%</div>
                        <div style="font-size: 16px; color: #555;">{headline}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Dimension Scores
            dimensions = coaching.get("dimensions", {})
            if dimensions:
                st.markdown("##### 📊 Performance Dimensions")
                
                dim_labels = {
                    "productivity": "🚀 Productivity",
                    "deadline_discipline": "⏰ Deadline Discipline",
                    "strategic_alignment": "🎯 Strategic Alignment",
                    "workload_balance": "⚖️ Workload Balance",
                    "momentum": "📈 Momentum"
                }
                
                # Display as columns with progress bars
                cols = st.columns(5)
                for i, (key, label) in enumerate(dim_labels.items()):
                    dim = dimensions.get(key, {})
                    score_val = dim.get("score", 0)
                    status_str = dim.get("status", "")
                    
                    with cols[i]:
                        st.metric(label.split(" ")[0], f"{score_val}%")
                        if "🟢" in status_str:
                            st.success(status_str, icon="✅")
                        elif "🔴" in status_str:
                            st.error(status_str, icon="🚨")
                        else:
                            st.warning(status_str, icon="⚠️")
                
                # Expandable insights per dimension
                with st.expander("💡 Detailed Insights & Actions", expanded=False):
                    for key, label in dim_labels.items():
                        dim = dimensions.get(key, {})
                        st.markdown(f"**{label}**")
                        st.info(f"📌 {dim.get('insight', 'N/A')}")
                        st.success(f"✅ Action: {dim.get('action', 'N/A')}")
                        st.markdown("---")
            
            # Top Priorities
            priorities = coaching.get("top_priorities", [])
            if priorities:
                st.markdown("##### 🎯 Top Priorities This Week")
                for i, p in enumerate(priorities, 1):
                    st.markdown(f"**{i}.** {p}")
            
            # Quick Wins
            quick_wins = coaching.get("quick_wins", [])
            if quick_wins:
                st.markdown("##### ⚡ Quick Wins")
                for win in quick_wins:
                    st.success(f"💡 {win}")
            
            # Watch Out
            watch_out = coaching.get("watch_out")
            if watch_out:
                st.markdown("##### ⚠️ Risk Alert")
                st.warning(f"🔔 {watch_out}")

@st.fragment
def render_report_content(data, username, mode):
    # Filter logic
    now = time.time() * 1000
    if mode == "Daily":
        # Start of today
        # Calculate midnight timestamp for today
        dt_now = datetime.fromtimestamp(now / 1000)
        dt_start = dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = dt_start.timestamp() * 1000
        period_label = "Today"
    else:
        # Weekly (7 days)
        start_time = now - (7 * 24 * 60 * 60 * 1000)
        period_label = "Last 7 Days"

    # CSS: Style YOUR EXISTING custom button as a circle (Dialog specific)
    st.markdown("""
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
    """, unsafe_allow_html=True)

    # Header with Close Button
    c_head, c_opts, c_close = st.columns([2, 1, 0.5])
    c_head.caption(f"Tasks with work recorded for: {mode} ({period_label})")
    
    # PDF Direction Toggle
    if "report_direction" not in st.session_state:
        st.session_state.report_direction = "LTR"
        
    with c_opts:
        st.session_state.report_direction = st.segmented_control(
            "PDF Direction",
            options=["LTR", "RTL"],
            default=st.session_state.report_direction,
            key=f"rep_dir_{mode}",
            label_visibility="collapsed"
        )

    with c_close:
        if st.button("✕", key=f"close_rep_{mode}"):
            if "active_report_mode" in st.session_state:
                del st.session_state.active_report_mode
            st.rerun()
    
    report_items = []
    objective_stats = {} # { "Objective Title": total_minutes }
    daily_minutes = {}   # { "YYYY-MM-DD": total_minutes }
    achievements = []    # Completed tasks
    
    # Iterate all nodes
    for nid, node in data["nodes"].items():
        # Check accomplishments
        if node.get("type") == "TASK" and node.get("progress") == 100:
            # We don't track completion date strictly, so we just list them if they have logs this week 
            # OR if we assume they were done recently. 
            # For this MVP, we only count them if they had work logged this period.
            pass

        logs = node.get("workLog", [])
        if not logs: continue
        
        has_log_this_period = False
        for log in logs:
            # Check if log is within range
            if log.get("endedAt", 0) >= start_time:
                has_log_this_period = True
                duration = log.get("durationMinutes", 0)
                # Aggregate by Objective
                obj_title = get_ancestor_objective(nid, data["nodes"])
                kr_title = get_ancestor_key_result(nid, data["nodes"])
                
                # Get deadline status if available
                deadline_status = "—"
                if node.get("deadline"):
                    from utils.deadline_utils import get_deadline_status
                    _, status_label, _ = get_deadline_status(node)
                    deadline_status = status_label
                
                log_date = datetime.fromtimestamp(log.get("endedAt", 0)/1000).strftime('%Y-%m-%d')
                
                report_items.append({
                    "Task": node.get("title", "Untitled"),
                    "Type": node.get("type", "TASK"),
                    "Date": log_date,
                    "Time": datetime.fromtimestamp(log.get("endedAt", 0)/1000).strftime('%H:%M'),
                    "Duration (m)": round(duration, 2),
                    "Deadline": deadline_status,
                    "Summary": log.get("summary", ""), # Capture summary
                    "Objective": obj_title,
                    "KeyResult": kr_title
                })
                
                objective_stats[obj_title] = objective_stats.get(obj_title, 0) + duration
                daily_minutes[log_date] = daily_minutes.get(log_date, 0) + duration

        if has_log_this_period and node.get("progress") == 100:
            achievements.append(node.get("title"))

    if not report_items:
        st.info("No work recorded in the this period.")
        return

    total = sum(item["Duration (m)"] for item in report_items)

    # === EXECUTIVE SUMMARY CARD ===
    if mode != "Daily":
        with st.container():
            st.markdown("### 📋 Executive Summary")
            
            # AI Summary
            if "report_summary" not in st.session_state:
                if st.button("✨ Generate AI Weekly Brief", type="primary", key="report_gen_ai"):
                     with st.spinner("Drafting executive summary..."):
                         from src.services.ai_service import generate_weekly_summary
                         # Prepare context
                         krs_updated = len(set(i["KeyResult"] for i in report_items))
                         obj_summary = [f"{k}: {int(v)}m" for k, v in objective_stats.items()]
                         
                         stats = {
                             "total_minutes": total,
                             "tasks_completed": len(achievements),
                             "krs_updated": krs_updated,
                             "objectives_text": obj_summary,
                             "key_achievements": achievements,
                             "work_logs_text": "\n".join([f"{i['Task']}: {i['Summary']}" for i in report_items[:30]])
                         }
                         
                         res = generate_weekly_summary(username, 
                                                     datetime.fromtimestamp(start_time/1000).strftime("%Y-%m-%d"),
                                                     datetime.now().strftime("%Y-%m-%d"),
                                                     stats)
                                                     
                         if "error" not in res:
                             st.session_state.report_summary = res
                             st.rerun()
                         else:
                             st.error(res["error"])
                             
            summary_res = st.session_state.get("report_summary")
            if summary_res:
                st.markdown(summary_res.get("summary_markdown"))
                
                # Metrics Row
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Focus", format_time(total))
                m2.metric("Tasks Completed", len(achievements))
                m3.metric("Key Highlights", len(summary_res.get("highlights", [])))
                
                with st.expander("📌 Highlights"):
                    for h in summary_res.get("highlights", []):
                        st.markdown(f"- {h}")
            else:
                st.info("Click above to generate an executive brief of your week.")

    st.markdown("---")

    # === TRENDS & ANALYSIS ===
    c_trend, c_achieve = st.columns([1.5, 1])
    
    with c_trend:
        if mode != "Daily":
            st.subheader("📈 Weekly Trends")
            if daily_minutes:
                # Sort dates
                sorted_dates = sorted(daily_minutes.keys())
                chart_data = {
                    "Date": sorted_dates,
                    "Hours": [daily_minutes[d]/60 for d in sorted_dates]
                }
                st.bar_chart(chart_data, x="Date", y="Hours", color="#4CAF50")
            else:
                st.caption("No trend data available.")
        else:
             st.info("Trend analysis available in Weekly Report.")

    with c_achieve:
        st.subheader("🏆 Achievements")
        if achievements:
            for ach in achievements:
                st.success(f"✅ {ach}")
        else:
            st.caption("No completed tasks this period.")
            
    # Deadline Health
    st.subheader("⚠️ Deadline Health")
    # Quick scan for overdue/at risk
    warnings = []
    for nid_dl, node_dl in data["nodes"].items():
        if node_dl.get("type") == "TASK" and node_dl.get("deadline") and node_dl.get("progress") < 100:
             from utils.deadline_utils import get_deadline_status
             _, label_dl, _ = get_deadline_status(node_dl)
             if "Overdue" in label_dl or "At Risk" in label_dl:
                 warnings.append(f"{label_dl} - {node_dl.get('title')}")
    
    if warnings:
        for w in warnings[:5]:
            st.error(w)
        if len(warnings) > 5:
            st.caption(f"...and {len(warnings)-5} more.")
    else:
        st.success("All tasks on track!", icon="🟢")


    # Filter Key Results (Needed for PDF)
    krs_list = []
    for nid_kr, node_kr in data["nodes"].items():
        if node_kr.get("type") == "KEY_RESULT":
            krs_list.append(node_kr)

    # PDF Export (Moved to Top)
    try:
        from src.services.pdf_service import generate_weekly_pdf_v2
        
        # Generate PDF
        # Only include key_results filter for PDF if mode is Weekly
        pdf_krs = krs_list if mode == "Weekly" else []
        
        # Determine Title
        pdf_title = "Daily Work Report" if mode == "Daily" else "Weekly Work Report"
        
        pdf_buffer = generate_weekly_pdf_v2(
            report_items, 
            objective_stats, 
            format_time(total), 
            pdf_krs, 
            st.session_state.report_direction, 
            title=pdf_title, 
            time_label=period_label,
            report_summary=st.session_state.get("report_summary"), # Pass AI summary
            achievements=achievements # Pass achievements list
        )
        
        if pdf_buffer:
             st.download_button(
                 label="📄 Export as PDF",
                 data=pdf_buffer,
                 file_name=f"{mode}_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                 mime="application/pdf",
                 key="report_pdf_download"
             )
    except Exception as e_pdf:
        st.error(f"PDF Generation Error: {e_pdf}")

    st.markdown("---")
    st.subheader("📝 Detailed Work Log")

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
            summary_txt = itm.get("Summary", "")
            
            table_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px;">{itm['Task']}</td>
                     <td style="padding: 8px; color: #555;">{itm['Objective']}</td>
                     <td style="padding: 8px; color: #555;">{itm['KeyResult']}</td>
                    <td style="padding: 8px; white-space: nowrap;">{itm['Date']} {itm['Time']}</td>
                    <td style="padding: 8px; text-align: right;">{itm['Duration (m)']}m</td>
                    <td style="padding: 8px; color: #555;">{summary_txt}</td>
                </tr>"""
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)
    
    st.metric(f"Total Time ({period_label})", format_time(total))
    
    st.markdown("---")
    st.subheader("Time Distribution by Objective")
    
    # Prepare data for chart/table
    # Sort stats by minutes descending first
    sorted_stats_obj = sorted(objective_stats.items(), key=lambda item: item[1], reverse=True)
    
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
        t_str_obj = format_time(mins_obj)
        
        obj_table_h += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px;">{t_obj}</td>
                <td style="padding: 8px; text-align: right;">{t_str_obj}</td>
                <td style="padding: 8px; text-align: right;">{p_str_obj}</td>
            </tr>"""
    obj_table_h += "</tbody></table>"
    st.markdown(obj_table_h, unsafe_allow_html=True)

    
    # --- SECTION: Key Result Strategic Status (Weekly Only) ---
    if mode == "Weekly":
        st.markdown("---")
        st.subheader("Key Result Strategic Status")
        
        if not krs_list:
            st.info("No Key Results found.")
        else:
            # Header Row
            h1, h2, h3, h4, h5, h6 = st.columns([2.5, 1.2, 1.2, 1.2, 1.2, 0.8])
            h1.markdown("**Key Result**")
            h2.markdown("**Progress**", help="Calculated from child tasks")
            h3.markdown("**Efficiency**", help="Completeness of work scope vs required")
            h4.markdown("**Effectiveness**", help="Quality of strategy and methods")
            h5.markdown("**Fulfillment**", help="Overall Score")
            h6.markdown("**Action**")
            
            st.markdown("<hr style='margin: 5px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
            
            from src.services.ai_service import analyze_node

            for kr_item in krs_list:
                # Prepare Data
                kr_title_text = kr_item.get("title", "Untitled")
                
                # Render Row Layout
                c1_kr, c2_kr, c3_kr, c4_kr, c5_kr, c6_kr = st.columns([2.5, 1.2, 1.2, 1.2, 1.2, 0.8])
                
                c1_kr.markdown(f"{kr_title_text}")
                c2_kr.markdown(f"{kr_item.get('progress', 0)}%")
                
                # Placeholders for dynamic updates
                p_eff = c3_kr.empty()
                p_qual = c4_kr.empty()
                p_full = c5_kr.empty()
                
                # Action Button
                do_update = c6_kr.button("🔄", key=f"upd_kr_{kr_item['id']}", help="Update Analysis")
                
                # Row Separator
                st.markdown("<hr style='margin: 5px 0; border: none; border-top: 0.5px solid #f0f0f0;'>", unsafe_allow_html=True)
                
                # Details Placeholder
                p_details = st.empty()

                # Helper to render current state to placeholders
                def render_kr_state(node_data):
                    an = node_data.get("geminiAnalysis")
                    eff_score = "N/A"
                    qual_score = "N/A"
                    fulfillment = "N/A"
                    
                    if an and isinstance(an, dict):
                        e_val = an.get('efficiency_score')
                        q_val = an.get('effectiveness_score')
                        o_val = an.get('overall_score')
                        
                        if e_val is not None: eff_score = f"{e_val}%"
                        if q_val is not None: qual_score = f"{q_val}%"
                        if o_val is not None: fulfillment = f"{o_val}%"

                    p_eff.markdown(eff_score)
                    p_qual.markdown(qual_score)
                    p_full.markdown(f"**{fulfillment}**")
                    
                    # Render Details
                    with p_details.container():
                         if an and isinstance(an, dict):
                             with st.expander("📝 Analysis Details"):
                                  if an.get('summary'):
                                       st.markdown(f"**Executive Summary:** {an.get('summary')}")
                                  
                                  c_d1, c_d2 = st.columns(2)
                                  with c_d1:
                                       if an.get('gap_analysis'):
                                            st.markdown(f"**Gap Analysis:**\n{an.get('gap_analysis')}")
                                  with c_d2:
                                       if an.get('quality_assessment'):
                                            st.markdown(f"**Quality Assessment:**\n{an.get('quality_assessment')}")

                # Initial Render
                render_kr_state(kr_item)
            
                # Handle Update
                if do_update:
                    with st.spinner("Analyzing..."):
                        from utils.storage import filter_nodes_by_cycle, update_node
                        cycle_id_kr = st.session_state.get("active_cycle_id")
                        filtered_nodes_kr = filter_nodes_by_cycle(data["nodes"], cycle_id_kr)
                        res_kr = analyze_node(kr_item['id'], filtered_nodes_kr)
                        if "error" in res_kr:
                            st.error(res_kr["error"])
                        else:
                            # Update Data
                            update_node(data, kr_item['id'], {"geminiAnalysis": res_kr}, username)
                            # Update UI immediately via placeholders (No Rerun)
                            kr_item["geminiAnalysis"] = res_kr # Update local var for rendering
                            render_kr_state(kr_item)

@st.fragment
def render_inspector_content(node_id, data, username):
    # CSS: Style YOUR EXISTING custom button as a circle (Dialog specific)
    st.markdown("""
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
    """, unsafe_allow_html=True)

    node = data["nodes"].get(node_id)
    if not node:
        st.error("Node not found")
        if st.button("Close", key=f"close_error_{node_id}"):
            if "active_inspector_id" in st.session_state:
                del st.session_state.active_inspector_id
            st.rerun()
        return

    title_insp = node.get('title', 'Untitled')
    progress_insp = node.get('progress', 0)
    node_type_insp = node.get('type', 'GOAL')
    has_children_insp = len(node.get("children", [])) > 0
    
    # Header logic with Close
    c_head_insp, c_close_insp = st.columns([0.92, 0.08])
    c_head_insp.markdown(f"### {TYPE_ICONS.get(node_type_insp, '')} {title_insp}")
    if c_close_insp.button("", icon=":material/close:", key=f"close_insp_{node_id}"):
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()
    
    from utils.storage import update_node, delete_node, start_timer, stop_timer, delete_work_log, get_total_time

    with st.form(key=f"edit_form_{node_id}"):
        new_title_insp = st.text_input("Title", value=title_insp)
        new_desc_insp = st.text_area("Description", value=node.get("description", ""))
        
        # Show Assignees (Editable for Admin/Manager)
        new_assignees_insp = node.get("assignees", [])
        if node_type_insp == "TASK":
             user_role_insp = st.session_state.get("user_role")
             if user_role_insp in ["admin", "manager"]:
                 from src.crud import get_all_users, get_team_members, get_user_by_username
                 potential_assignees = []
                 if user_role_insp == "admin":
                     all_users_insp = get_all_users()
                     potential_assignees = all_users_insp
                 elif user_role_insp == "manager":
                     manager_id_insp = st.session_state.get("user_id")
                     from src.crud import get_user_by_id
                     manager_obj = get_user_by_id(manager_id_insp)
                     potential_assignees = get_team_members(manager_id_insp)
                     if manager_obj: potential_assignees.append(manager_obj)
                 
                 # Map display names to usernames
                 member_map = {f"{u.display_name} ({u.username})": u.username for u in potential_assignees}
                 current_opts_insp = [lab for lab, un in member_map.items() if un in new_assignees_insp]
                 
                 selected_labs_insp = st.multiselect(
                     "Assign To", 
                     options=list(member_map.keys()),
                     default=current_opts_insp,
                     key=f"assign_multi_{node_id}"
                 )
                 new_assignees_insp = [member_map[l] for l in selected_labs_insp]
             else:
                 # Read-only for Members
                 if new_assignees_insp:
                     st.info(f"👥 **Assigned To:** {', '.join(new_assignees_insp)}")

        col1_insp, col2_insp = st.columns(2)
        with col1_insp:
            p_prog_cont = st.empty()
            if has_children_insp:
                 p_prog_cont.metric("Progress (Calculated)", value=f"{progress_insp}%")
                 new_progress_insp = progress_insp
            else:
                 new_progress_insp = p_prog_cont.slider("Progress (Manual)", 0, 100, value=progress_insp)
        
        with col2_insp:
            idx_insp = TYPES.index(node_type_insp) if node_type_insp in TYPES else 0
            new_type_insp = st.selectbox("Type", TYPES, index=idx_insp, key=f"type_sel_{node_id}")
            
        # GOAL Specific Cycle Assignment
        new_cycle_id_insp = node.get("cycle_id")
        new_strat_tags_input = ""
        if node_type_insp == "GOAL":
            st.markdown("---")
            st.caption("📅 Cycle Assignment")
            from src.crud import get_all_cycles
            all_cycles_insp = get_all_cycles()
            cycle_titles_insp = [c.title for c in all_cycles_insp]
            cycle_ids_insp = [c.id for c in all_cycles_insp]
            
            try:
                curr_idx = cycle_ids_insp.index(new_cycle_id_insp)
            except:
                curr_idx = 0
                
            sel_cyc = st.selectbox("Assign to Cycle", options=cycle_titles_insp, index=curr_idx, key=f"cyc_assign_{node_id}")
            new_cycle_id_insp = all_cycles_insp[cycle_titles_insp.index(sel_cyc)].id
            
            st.caption("♟️ Strategy Tags")
            curr_strats = node.get("strategy_tags", [])
            new_strat_tags_input = st.text_input("Add Strategy Tags (comma-separated)", value=", ".join(curr_strats), key=f"strat_tags_{node_id}")

        # KEY_RESULT Specific Metrics
        new_target_insp = node.get("target_value", 100.0)
        new_curr_insp = node.get("current_value", 0.0)
        new_unit_insp = node.get("unit", "%")
        new_init_tags_input = ""
        
        if node_type_insp == "KEY_RESULT":
            st.markdown("---")
            st.caption("📈 Progress Metrics")
            mc1_in, mc2_in, mc3_in = st.columns(3)
            new_target_insp = mc1_in.number_input("Target Value", value=float(new_target_insp), key=f"target_{node_id}")
            new_curr_insp = mc2_in.number_input("Current Value", value=float(new_curr_insp), key=f"curr_val_{node_id}")
            new_unit_insp = mc3_in.text_input("Unit", value=new_unit_insp, key=f"unit_{node_id}")
            
            if new_target_insp > 0:
                calc_p = int((new_curr_insp / new_target_insp) * 100)
                calc_p = max(0, min(100, calc_p))
                if not has_children_insp:
                    new_progress_insp = calc_p
                    st.info(f"Calculated Progress: {new_progress_insp}%")
            
            st.caption("⚡ Initiative Tags")
            curr_inits = node.get("initiative_tags", [])
            new_init_tags_input = st.text_input("Add Initiative Tags (comma-separated)", value=", ".join(curr_inits), key=f"init_tags_{node_id}")

        user_role_perm = st.session_state.get("user_role")
        can_save_insp = (user_role_perm in ["admin", "manager"]) or (username == node.get("user_id"))
        
        if st.form_submit_button("💾 Save Changes", disabled=not can_save_insp):
            s_tags = [t.strip() for t in new_strat_tags_input.split(",") if t.strip()] if node_type_insp == "GOAL" else node.get("strategy_tags", [])
            i_tags = [t.strip() for t in new_init_tags_input.split(",") if t.strip()] if node_type_insp == "KEY_RESULT" else node.get("initiative_tags", [])
            
            update_node(data, node_id, {
                "title": new_title_insp,
                "description": new_desc_insp,
                "progress": new_progress_insp,
                "type": new_type_insp,
                "target_value": new_target_insp,
                "current_value": new_curr_insp,
                "unit": new_unit_insp,
                "cycle_id": new_cycle_id_insp,
                "strategy_tags": s_tags,
                "initiative_tags": i_tags,
                "assignees": new_assignees_insp
            }, username)
            st.rerun()

    if node_type_insp == "TASK":
        st.markdown("---")
        st.write("### ⏱️ Time Tracking")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
             u_role = st.session_state.get("user_role", "member")
             is_run = node.get("timerStartedAt") is not None
             if is_run:
                  start_t = node.get("timerStartedAt")
                  elap = int((time.time() * 1000 - start_t) / 60000)
                  st.info(f"Timer Running: {elap}m")
                  
             can_track = (u_role == "admin") or (u_role == "manager" and (not node.get("created_by_username") or node.get("created_by_username") == username)) or (u_role == "member" and (node.get("created_by_username") in [username, st.session_state.get("manager_username")]))
             
             if can_track:
                  if is_run:
                       c_a1, c_a2 = st.columns(2)
                       if c_a1.button("Open Timer", icon=":material/timer:", key=f"open_t_{node_id}"):
                           st.session_state.active_timer_node_id = node_id
                           if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                           st.rerun()
                       if c_a2.button("Stop", icon=":material/stop_circle:", key=f"stop_t_{node_id}"):
                           stop_timer(data, node_id, username)
                           if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
                           st.rerun()
                  else:
                       if st.button("Start Timer", icon=":material/play_circle:", key=f"start_t_{node_id}"):
                           start_timer(data, node_id, username)
                           st.session_state.active_timer_node_id = node_id
                           if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                           st.rerun()
        with col_t2:
            tot = get_total_time(node_id, data["nodes"])
            st.metric("Total Time", format_time(tot))

    if node_type_insp == "TASK":
        st.markdown("---")
        st.write("### 📅 Schedule")
        from utils.deadline_utils import get_deadline_status
        # Start Date
        curr_sd_iso = node.get("start_date")
        curr_sd = datetime.fromisoformat(curr_sd_iso).date() if curr_sd_iso else None
        
        # Deadline
        curr_dl = node.get("deadline")
        curr_d = datetime.fromtimestamp(curr_dl / 1000).date() if curr_dl else None
        
        col_sch1, col_sch2 = st.columns(2)
        with col_sch1:
            new_sd = st.date_input("Start Date", value=curr_sd, key=f"sd_inp_{node_id}")
            new_sd_ts = int(datetime.combine(new_sd, datetime.min.time()).timestamp() * 1000) if new_sd else None # Not used directly if we store ISO string or datetime
            # Storage update_node expects simple dict, map to 'start_date' expects datetime object or string? 
            # In update_node -> crud.update_task -> start_date: datetime.
            # So passing datetime object is best for crud, but storage.py update_node maps JSON updates.
            # Wait, storage.py update_node maps to sql_updates. 
            # If I pass a datetime object to update_node, storage.py needs to handle it?
            # Storage update_node (line 550) logic:
            # if model_class == Task: update_task(sql_node.id, **sql_updates)
            # And it maps keys. My update to storage.py added "start_date": "start_date" to mapping.
            # And `update_task` expects `datetime`.
            # If I pass `new_sd` (date), I should combine it to datetime.
            
            new_sd_dt = datetime.combine(new_sd, datetime.min.time()) if new_sd else None
            
            if st.button("💾 Save Start Date", key=f"save_sd_{node_id}"):
                update_node(data, node_id, {"start_date": new_sd_dt}, username)
                st.rerun()

        with col_sch2:
            new_d = st.date_input("Due Date", value=curr_d, key=f"dl_inp_{node_id}")
            new_dl_ts = int(datetime.combine(new_d, datetime.max.time()).timestamp() * 1000) if new_d else None
            
            if st.button("💾 Save Due Date", key=f"save_dl_{node_id}"):
                update_node(data, node_id, {"deadline": new_dl_ts}, username)
                st.rerun()

        # Clear Buttons Row
        clr1, clr2 = st.columns(2)
        if curr_sd and clr1.button("🗑️ Clear Start", key=f"clear_sd_{node_id}"):
             update_node(data, node_id, {"start_date": None}, username)
             st.rerun()
        if curr_dl and clr2.button("🗑️ Clear Due", key=f"clear_dl_{node_id}"):
             update_node(data, node_id, {"deadline": None}, username)
             st.rerun()

        if curr_dl:
             st_code, st_lbl, hlth = get_deadline_status(node)
             st.metric("Deadline Status", st_lbl)
             st.progress(hlth / 100)

    if node_type_insp == "TASK":
         st.markdown("---")
         st.markdown("### 📜 Work History")
         w_log = node.get("workLog", [])
         if w_log:
             w_sorted = sorted(w_log, key=lambda x: x.get("endedAt", 0), reverse=True)
             for l in w_sorted:
                 d_str = datetime.fromtimestamp(l.get("endedAt", 0)/1000).strftime('%Y-%m-%d %H:%M')
                 dur_str = f"{round(l.get('durationMinutes', 0), 1)}m"
                 sm = l.get("summary", "") or "-"
                 st.write(f"**{d_str}** | {dur_str} | {sm}")

    if node_type_insp == "KEY_RESULT":
        st.markdown("---")
        st.markdown("### 🧠 AI Strategic Analysis")
        if st.button("✨ Run Analysis", type="primary", key=f"run_ai_insp_{node_id}"):
             with st.spinner("Analyzing..."):
                 from utils.storage import filter_nodes_by_cycle
                 cyc_id_ai = st.session_state.get("active_cycle_id")
                 filtered_ai = filter_nodes_by_cycle(data["nodes"], cyc_id_ai)
                 from src.services.ai_service import analyze_node
                 res_ai = analyze_node(node_id, filtered_ai)
                 if "error" not in res_ai:
                     update_node(data, node_id, {"geminiAnalysis": res_ai["analysis"], "geminiLastSnapshot": res_ai["snapshot"]}, username)
                     st.rerun()
        
        analysis_insp = node.get("geminiAnalysis")
        if analysis_insp and isinstance(analysis_insp, dict):
            st.metric("Efficiency", f"{analysis_insp.get('efficiency_score')}%")
            st.info(analysis_insp.get("summary", ""))

    st.markdown("---")
    user_role_del = st.session_state.get("user_role")
    can_delete = (user_role_del == "admin") or (username == node.get("user_id"))
    
    if can_delete:
        if st.button("🗑️ Delete Entity", type="primary", key=f"del_insp_{node_id}"):
            delete_node(data, node_id, username)
            if "active_inspector_id" in st.session_state:
                del st.session_state.active_inspector_id
            st.rerun()

def render_card(node_id, data, username):
    node = data["nodes"].get(node_id)
    if not node: return

    title = node.get("title", "Untitled")
    progress = node.get("progress", 0)
    node_type = node.get("type", "GOAL")
    has_children = len(node.get("children", [])) > 0
    is_leaf = node_type == "TASK" # Tasks don't have navigable children in our map
    
    from utils.storage import get_total_time, start_timer, update_node
    
    # CSS Frame
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        with c1:
            # Clickable Title => Navigate
            label = f"{TYPE_ICONS.get(node_type, '')} {title}"
            
            # Subtitle stats
            stats = f"📊 {progress}% | {node_type.replace('_',' ').title()}"
            if node_type == "TASK":
                t_card = get_total_time(node_id, data["nodes"])
                stats += f" | ⏱️ {format_time(t_card)}"
                # Add deadline indicator
                if node.get("deadline"):
                    from utils.deadline_utils import get_deadline_status
                    _, status_label, _ = get_deadline_status(node)
                    stats += f" | {status_label}"
            
            st.markdown(f"**{label}**")
            st.caption(stats)

            # Show Strategy Tags for Goals
            if node_type == "GOAL":
                strat_tags = node.get("strategy_tags", [])
                if strat_tags:
                    tags_html = " ".join([f"<span style='background-color:#1E88E5;color:white;padding:2px 8px;border-radius:10px;font-size:0.75em;margin-right:4px;'>♟️ {t}</span>" for t in strat_tags])
                    st.markdown(tags_html, unsafe_allow_html=True)
            
            # Show Initiative Tags for Key Results
            if node_type == "KEY_RESULT":
                init_tags = node.get("initiative_tags", [])
                if init_tags:
                    tags_html = " ".join([f"<span style='background-color:#8E24AA;color:white;padding:2px 8px;border-radius:10px;font-size:0.75em;margin-right:4px;'>⚡ {t}</span>" for t in init_tags])
                    st.markdown(tags_html, unsafe_allow_html=True)
            
            # Tags Row: Creator and Owner (if applicable)
            user_role = st.session_state.get("user_role", "member")
            tags_row_html = ""
            
            # ✍️ Creator Tag (All items)
            creator_name = node.get("created_by_display_name") or node.get("user_id") or node.get("created_by_username") or "Unknown"
            if creator_name == "admin":
                creator_name = "Administrator"
            
            tags_row_html += f"<span style='background-color:#F5F5F5;color:#616161;padding:2px 8px;border-radius:10px;font-size:0.75em;margin-right:4px;border:1px solid #e0e0e0;'>✍️ {creator_name}</span>"
            
            # 👤 Owner Tag (Goals only, for Admin/Manager viewing team)
            if user_role in ["admin", "manager"] and node_type == "GOAL":
                owner_name = node.get("owner_display_name") or node.get("user_id", "Unknown")
                tags_row_html += f"<span style='background-color:#E3F2FD;color:#1565C0;padding:2px 8px;border-radius:10px;font-size:0.75em;'>👤 {owner_name}</span>"
            
            # 📥 Assigned Tag (Virtual nodes)
            if node.get("is_virtual"):
                tags_row_html += f"<span style='background-color:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:10px;font-size:0.75em;margin-left:4px;border:1px solid #c8e6c9;'>📥 Assigned by Manager</span>"

            if tags_row_html:
                st.markdown(f"<div style='margin-top:4px;'>{tags_row_html}</div>", unsafe_allow_html=True)
            
            # --- SELF HEALING ---
            parent_id = node.get("parentId")
            if parent_id:
                parent_node = data["nodes"].get(parent_id)
                if parent_node:
                    ptype = parent_node.get("type", "").upper()
                    expected_type = CHILD_TYPE_MAP.get(ptype)
                    if expected_type and node_type != expected_type:
                        action_lbl = "➡️ Enable Tasks Level" if expected_type == "INITIATIVE" else f"🔧 Fix Type (to {expected_type.replace('_',' ').title()})"
                        if st.button(action_lbl, key=f"fix_{node_id}"):
                            update_node(data, node_id, {"type": expected_type}, username)
                            st.rerun()

        with c2:
             # Timer Controls (If Task)
             if node_type == "TASK":
                 if node.get("timerStartedAt") is not None:
                     start_ts_c = node.get("timerStartedAt", 0)
                     elapsed_c = int((time.time() * 1000 - start_ts_c) / 60000)
                     if st.button(f"Running ({elapsed_c}m)", icon=":material/timer:", key=f"open_t_c_{node_id}"):
                         st.session_state.active_timer_node_id = node_id
                         if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                         st.rerun()
                 else:
                     if st.button("Start Timer", icon=":material/play_arrow:", key=f"start_c_{node_id}"):
                         start_timer(data, node_id, username)
                         st.session_state.active_timer_node_id = node_id
                         if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                         st.rerun()
             
             if st.button("Inspect", icon=":material/search:", key=f"inspect_{node_id}"):
                 st.session_state.active_inspector_id = node_id
                 if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
                 st.rerun()
             
             # View Map button
             if has_children:
                  if st.button("Map", icon=":material/account_tree:", key=f"map_{node_id}"):
                       from src.ui.dialogs import render_mindmap_dialog
                       render_mindmap_dialog(node_id, data)
                  
        with c3:
            # Navigation Button ("Open")
            if not is_leaf:
                if st.button("Open", icon=":material/arrow_forward:", key=f"nav_{node_id}"):
                    navigate_to(node_id)
            
            # AI Analysis Quick Button
            if node_type == "KEY_RESULT":
                if st.button("AI", icon=":material/psychology:", key=f"ai_c_{node_id}"):
                    from src.services.ai_service import analyze_node
                    from utils.storage import filter_nodes_by_cycle
                    cyc_id_c = st.session_state.get("active_cycle_id")
                    filtered_c = filter_nodes_by_cycle(data["nodes"], cyc_id_c)
                    with st.spinner("🧠 Analyzing..."):
                        res_c = analyze_node(node_id, filtered_c)
                        if "error" not in res_c:
                            update_node(data, node_id, {"geminiAnalysis": res_c["analysis"], "geminiLastSnapshot": res_c["snapshot"]}, username)
                            st.rerun()

def render_level(data, username, root_ids=None):
    stack = st.session_state.nav_stack
    
    # Determine what to show
    if not stack:
        items_lvl = root_ids if root_ids is not None else data.get("rootIds", [])
        level_name = "Goals"
        current_node_lvl = None
    else:
        parent_id_lvl = stack[-1]
        current_node_lvl = data["nodes"].get(parent_id_lvl)
        if not current_node_lvl:
            st.error("Node not found")
            st.session_state.nav_stack.pop() # Recovery
            st.rerun()
            return
            
        items_lvl = current_node_lvl.get("children", [])
        ptype_lvl = current_node_lvl.get("type")
        ctype_lvl = CHILD_TYPE_MAP.get(ptype_lvl)
        
        if ctype_lvl:
             normalized_lvl = ctype_lvl.replace('_',' ').title()
             if normalized_lvl.endswith('y'):
                 level_name = normalized_lvl[:-1] + "ies"
             elif normalized_lvl.endswith('s'):
                 level_name = normalized_lvl
             else:
                 level_name = f"{normalized_lvl}s"
        else:
             level_name = "Items"

    # Header
    render_breadcrumbs(data)
    
    from utils.storage import add_node
    
    if current_node_lvl:
        st.markdown(f"## {level_name}")
        c_type_lvl = current_node_lvl.get("type", "").upper()
        ch_type_lvl = CHILD_TYPE_MAP.get(c_type_lvl)
        
        if ch_type_lvl:
             u_role_lvl = st.session_state.get("user_role", "member")
             can_add_lvl = (u_role_lvl in ["admin", "manager"]) or (ch_type_lvl == "TASK" and username == current_node_lvl.get("user_id"))
             
             if can_add_lvl:
                  norm_btn_lvl = ch_type_lvl.replace('_',' ').title()
                  if st.button(f"➕ New {norm_btn_lvl}", key=f"add_btn_{current_node_lvl['id']}"):
                      if ch_type_lvl == "TASK":
                          from src.ui.dialogs import render_create_task_dialog
                          render_create_task_dialog(data, current_node_lvl["id"], username)
                      else:
                          add_node(data, current_node_lvl["id"], ch_type_lvl, f"New {norm_btn_lvl}", "", username, cycle_id=st.session_state.active_cycle_id)
                          st.rerun()
    else:
        st.markdown(f"## {level_name}")
        if st.session_state.get("user_role") in ["admin", "manager"]:
            if st.button("➕ New Goal"):
                cid_lvl = st.session_state.get("active_cycle_id")
                if cid_lvl:
                    add_node(data, None, "GOAL", "New Goal", "", username, cycle_id=cid_lvl)
                    st.rerun()

    st.markdown("---")
    if not items_lvl:
        st.info("No items here yet.")
    
    for i_id in items_lvl:
        render_card(i_id, data, username)
