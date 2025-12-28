import streamlit as st
import sys
import os
import time
from datetime import datetime

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, load_all_data, load_team_data, save_data, add_node, delete_node, update_node, update_node_progress, export_data, import_data, start_timer, stop_timer, get_total_time, delete_work_log
from utils.styles import apply_custom_fonts
from src.database import init_database
from src.crud import (
    get_all_cycles, create_cycle, get_active_cycles,
    create_check_in, get_krs_needing_checkin, get_check_ins,
    get_leadership_metrics, update_cycle, delete_cycle,
    # User Auth
    authenticate_user, get_all_users, create_user, update_user,
    reset_user_password, get_team_members, ensure_admin_exists
)
from src.models import UserRole
import plotly.graph_objects as go
import pandas as pd

# Import streamlit-agraph for mind map visualization
from streamlit_agraph import agraph, Node, Edge, Config

st.set_page_config(page_title="OKR Tracker", layout="wide")
apply_custom_fonts()

# Hierarchy types (4 levels: Goal → Objective → Key Result → Task)
# Note: Strategy and Initiative are now TAGS, not navigable levels
TYPES = ["GOAL", "OBJECTIVE", "KEY_RESULT", "TASK"]

CHILD_TYPE_MAP = {
    "GOAL": "OBJECTIVE",
    "OBJECTIVE": "KEY_RESULT",
    "KEY_RESULT": "TASK",
    "TASK": None 
}

TYPE_ICONS = {
    "GOAL": "🏁",
    "STRATEGY": "♟️",
    "OBJECTIVE": "🎯",
    "KEY_RESULT": "📊",
    "INITIATIVE": "⚡",
    "TASK": "📋"
}

# Colors for mind map visualization
TYPE_COLORS = {
    "GOAL": "#E53935",       # Red
    "STRATEGY": "#1E88E5",   # Blue
    "OBJECTIVE": "#43A047",  # Green
    "KEY_RESULT": "#FB8C00", # Orange
    "INITIATIVE": "#8E24AA", # Purple
    "TASK": "#757575"        # Gray
}

# Size by hierarchy depth (larger for higher-level nodes)
TYPE_SIZES = {
    "GOAL": 35,
    "STRATEGY": 30,
    "OBJECTIVE": 25,
    "KEY_RESULT": 22,
    "INITIATIVE": 18,
    "TASK": 15
}

def format_time(minutes):
    if not minutes: return "0m"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

def build_graph_from_node(node_id, data):
    """
    Recursively build a graph (nodes and edges) from a starting node.
    Returns (list of Node, list of Edge) for streamlit-agraph.
    """
    nodes_list = []
    edges_list = []
    visited = set()
    
    def traverse(nid, parent_nid=None):
        if nid in visited or nid not in data["nodes"]:
            return
        visited.add(nid)
        
        node = data["nodes"][nid]
        node_type = node.get("type", "GOAL")
        title = node.get("title", "Untitled")
        progress = node.get("progress", 0)
        
        # Create label with icon and progress
        icon = TYPE_ICONS.get(node_type, "")
        label = f"{icon} {title}\n({progress}%)"
        
        # Create the Node
        nodes_list.append(Node(
            id=nid,
            label=label,
            size=TYPE_SIZES.get(node_type, 20),
            color=TYPE_COLORS.get(node_type, "#666666"),
            title=f"{node_type.replace('_', ' ').title()}: {title}\nProgress: {progress}%"
        ))
        
        # Create edge from parent
        if parent_nid:
            edges_list.append(Edge(
                source=parent_nid,
                target=nid,
                color="#888888"
            ))
        
        # Traverse children
        for child_id in node.get("children", []):
            traverse(child_id, nid)
    
    traverse(node_id)
    return nodes_list, edges_list

@st.dialog("Manage OKR Cycles", width="medium")
def render_manage_cycles_dialog():
    st.write("Add or activate/deactivate your OKR cycles.")
    
    with st.form("new_cycle_form"):
        st.subheader("Add New Cycle")
        new_title = st.text_input("Cycle Title", placeholder="e.g. Q2 2026")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            new_start = st.date_input("Start Date")
        with col_d2:
            new_end = st.date_input("End Date")
        
        if st.form_submit_button("➕ Create Cycle"):
            if new_title:
                create_cycle(
                    title=new_title,
                    start_date=datetime.combine(new_start, datetime.min.time()),
                    end_date=datetime.combine(new_end, datetime.min.time()),
                    is_active=True
                )
                st.success(f"Cycle '{new_title}' created!")
                st.rerun()
            else:
                st.error("Title is required.")

    st.markdown("---")
    st.subheader("Existing Cycles")
    all_cycles = get_all_cycles()
    for c in all_cycles:
        with st.expander(f"{'✅ ' if c.is_active else '⚪ '}{c.title}"):
            with st.form(key=f"edit_cycle_{c.id}"):
                edit_title = st.text_input("Title", value=c.title)
                col1, col2 = st.columns(2)
                with col1:
                    edit_start = st.date_input("Start Date", value=c.start_date.date(), key=f"start_{c.id}")
                with col2:
                    edit_end = st.date_input("End Date", value=c.end_date.date(), key=f"end_{c.id}")
                
                edit_active = st.checkbox("Active Cycle", value=c.is_active)
                
                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.form_submit_button("💾 Save Changes", type="primary"):
                    update_cycle(
                        cycle_id=c.id,
                        title=edit_title,
                        start_date=datetime.combine(edit_start, datetime.min.time()),
                        end_date=datetime.combine(edit_end, datetime.min.time()),
                        is_active=edit_active
                    )
                    st.success("Cycle updated!")
                    st.rerun()
                
                if btn_col2.form_submit_button("🗑️ Delete", type="secondary"):
                    if delete_cycle(c.id):
                        st.success("Cycle deleted!")
                        st.rerun()
                    else:
                        st.error("Cannot delete cycle. Please remove its Goals first to avoid data loss.")

# Render the mind map visualization in a dialog.
@st.dialog("Hierarchy Map", width="large")
def render_mindmap_dialog(node_id, data):
    """Render the mind map visualization in a dialog."""
    node = data["nodes"].get(node_id)
    if not node:
        st.error("Node not found")
        return
    
    st.markdown(f"### Hierarchy of: {node.get('title', 'Untitled')}")
    st.caption("Drag to pan, scroll to zoom. Nodes are color-coded by type.")
    
    # Build graph
    nodes_list, edges_list = build_graph_from_node(node_id, data)
    
    if not nodes_list:
        st.warning("No nodes to display")
        return
    
    # Configure the graph
    config = Config(
        width=800,
        height=500,
        directed=True,
        physics=True,
        hierarchical=True,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
        node={"labelProperty": "label"},
        link={"labelProperty": "label", "renderLabel": False}
    )
    
    # Render the graph
    agraph(nodes=nodes_list, edges=edges_list, config=config)
    
    # Legend
    st.markdown("---")
    st.markdown("**Legend:**")
    legend_cols = st.columns(6)
    for i, (ntype, color) in enumerate(TYPE_COLORS.items()):
        with legend_cols[i]:
            icon = TYPE_ICONS.get(ntype, "")
            st.markdown(f"<span style='color:{color};font-size:1.2em;'>{icon}</span> {ntype.replace('_', ' ').title()}", unsafe_allow_html=True)

# --- State Management ---
if "nav_stack" not in st.session_state:
    st.session_state.nav_stack = [] # List of node IDs. Empty = Root view.

# --- Components ---

@st.dialog("⏱️ Focus Timer")
def render_timer_dialog(node_id, data, username):
    render_timer_content(node_id, data, username)

@st.fragment(run_every=1)
def render_timer_content(node_id, data, username):
    node = data["nodes"].get(node_id)
    if not node:
        st.error("Task not found!")
        time.sleep(2)
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        st.rerun()
        return

    # Check if timer is still running
    start_ts = node.get("timerStartedAt")
    if not start_ts:
        st.success("Timer stopped successfully!")
        if st.button("Close"):
             if "active_timer_node_id" in st.session_state:
                 del st.session_state.active_timer_node_id
             st.rerun()
        return

    # Calculate elapsed
    elapsed_ms = (time.time() * 1000) - start_ts
    elapsed_sec = int(elapsed_ms / 1000)
    
    hours = elapsed_sec // 3600
    minutes = (elapsed_sec % 3600) // 60
    seconds = elapsed_sec % 60
    
    time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
    
    st.markdown(f"<div class='timer-task-title'>{node.get('title', 'Unknown Task')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='timer-display'>{time_str}</div>", unsafe_allow_html=True)
    
    # Summary Input
    summary = st.text_area("What did you work on?", placeholder="Brief summary of your session...", height=80, key=f"sum_{node_id}")

    # Controls
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Stop & Save", icon=":material/stop_circle:", key=f"stop_dlg_{node_id}", use_container_width=True, type="primary"):
            stop_timer(data, node_id, username, summary=summary)
            if "active_timer_node_id" in st.session_state:
                del st.session_state.active_timer_node_id
            st.rerun() 
            
    with col2:
         if st.button("Minimize", icon=":material/minimize:", key=f"min_dlg_{node_id}", use_container_width=True):
             if "active_timer_node_id" in st.session_state:
                 del st.session_state.active_timer_node_id
             st.rerun()

def render_login():
    st.markdown("## 🔐 Login to OKR Tracker")
    st.info("👋 Welcome! Please enter your credentials to access your data.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Username", placeholder="e.g. admin")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            if username.strip() and password:
                user = authenticate_user(username.strip(), password)
                if user:
                    # Store user info in session
                    st.session_state["user_id"] = user.id
                    st.session_state["username"] = user.username
                    st.session_state["display_name"] = user.display_name
                    st.session_state["user_role"] = user.role.value
                    st.success(f"Welcome, {user.display_name}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            else:
                st.error("Please enter both username and password.")


def navigate_to(node_id):
    """Push node to stack."""
    st.session_state.nav_stack.append(node_id)
    st.rerun()

def navigate_back_to(index):
    """Pop stack to specific index."""
    if index < 0:
        st.session_state.nav_stack = []
    else:
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

@st.fragment
def render_report_content(data, username, mode="Weekly"): 
    # 1. CSS: Hide native close button AND style our custom button as a circle
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

        /* 3. The Visual Background Layer 
           - We use the modal container to paint the black screen.
           - We set pointer-events: none so clicks pass through it (bypassing Streamlit's close listener).
        */
        div[data-baseweb="modal"] {
            background-color: rgba(0, 0, 0, 0.5);
            pointer-events: none; /* Look but don't touch */
        }

        /* 4. The "Invisible Click Shield" 
           - We attach a massive invisible layer to the Dialog Box itself.
           - We use huge negative margins to make it cover the whole screen.
           - Because it is a child of "dialog", clicking it reports the target as "dialog", so Streamlit does NOT close.
           - We set pointer-events: auto to CATCH the click so it doesn't fall through to the app.
        */
        div[role="dialog"]::before {
            content: "";
            position: absolute;
            top: -500vh;
            left: -500vw;
            width: 1000vw;
            height: 1000vh;
            background: transparent; /* Invisible */
            z-index: -1;             /* Behind the dialog content */
            cursor: default;
            pointer-events: auto;    /* Catch the click! */
        }

        /* 5. Ensure the Dialog Box is Interactive */
        div[role="dialog"] {
            overflow: visible !important; /* Allow the shield to extend outside */
            pointer-events: auto;         /* Re-enable clicking inside the box */
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

    # 2. Header Layout: Caption on Left, Circle Button on Right
    col_header, col_close = st.columns([9.2, 0.8])
    
    with col_header:
        # Determine Period Label
        now = time.time() * 1000
        period_label = "Today" if mode == "Daily" else "Last 7 Days"
        st.caption(f"Tasks with work recorded for: {mode} ({period_label})")

    with col_close:
        # The Circular Close Button
        if st.button("", icon=":material/close:", key=f"close_report_circle_{mode}", type="secondary", help="Close"):
            if "active_report_mode" in st.session_state:
                del st.session_state.active_report_mode
            st.rerun()

    # Initialize direction state if not set
    if "report_direction" not in st.session_state:
        st.session_state.report_direction = "RTL"
        
    # Toggle for direction
    c_label, c_pills, c_rest = st.columns([1.2, 1.5, 5])
    with c_label:
        st.markdown("<p style='padding-top: 10px; font-weight: bold; white-space: nowrap;'>Page Layout</p>", unsafe_allow_html=True)
    with c_pills:
        new_dir = st.pills(
            "Page Layout",
            options=["LTR", "RTL"],
            default=st.session_state.report_direction,
            selection_mode="single",
            key=f"layout_pills_{mode}", # Unique key per mode
            label_visibility="collapsed"
        )
        
    if new_dir and new_dir != st.session_state.report_direction:
            st.session_state.report_direction = new_dir
            st.rerun()

    # Enforce RTL Layout for this dialog Only if selected
    if st.session_state.report_direction == "RTL":
        st.markdown("""
            <style>
            div[role="dialog"] {
                direction: rtl;
                text-align: right;
            }
            /* Ensure specific elements inherit or enforce RTL */
            div[role="dialog"] .stMarkdown, div[role="dialog"] p, 
            div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3,
            div[role="dialog"] .stMetricValue, div[role="dialog"] .stMetricLabel {
                direction: rtl;
                text-align: right;
                font-family: 'Vazirmatn', sans-serif !important;
            }
            /* Align columns content to right */
            div[role="dialog"] [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
                direction: rtl; 
            }
            </style>
        """, unsafe_allow_html=True)

@st.dialog("🧭 Strategic Health Dashboard", width="large")
def render_leadership_dashboard_dialog(username):
    # CSS: Hide native X and make dialog strictly modal
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] {
            display: none;
        }
        div[data-baseweb="modal-backdrop"] {
            display: none;
        }
        div[data-baseweb="modal"] {
            background-color: rgba(0, 0, 0, 0.5);
            pointer-events: none;
        }
        div[role="dialog"]::before {
            content: "";
            position: absolute;
            top: -500vh; left: -500vw; width: 1000vw; height: 1000vh;
            background: transparent;
            z-index: -1;
            pointer-events: auto;
        }
        div[role="dialog"] {
            overflow: visible !important;
            pointer-events: auto;
        }
        /* Style the custom button in the header */
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button {
            border-radius: 50%;
            border: 1px solid #e0e0e0;
            width: 35px; height: 35px;
            padding: 0 !important;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            background-color: white;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Header with Close button
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### Efficiency vs. Effectiveness Analysis")
    if c_close.button("", icon=":material/close:", key="close_dash_dialog"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()
    
    render_leadership_dashboard_content(username)

def render_leadership_dashboard_content(username):
    # (Title is now in the dialog header)
    
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle to view insights.")
        return
    
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
                help="Filter dashboard metrics to show data for selected members only"
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
    
    # Get leadership metrics (uses SQL - for single user or first selected)
    metrics = get_leadership_metrics(selected_members[0], cycle_id)
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
        
        st.plotly_chart(fig_progress, use_container_width=True)
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
            
            st.plotly_chart(fig_deadline, use_container_width=True)
        st.markdown("---")
    
    # === STRATEGIC ALIGNMENT MATRIX ===
    st.markdown("#### 📊 Strategic Alignment Matrix")
    
    data = metrics["heatmap_data"]
    if data:
        df = pd.DataFrame(data)
        
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
        
        st.plotly_chart(fig, use_container_width=True)
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
            status_code, _, _ = get_deadline_status(node)
            if status_code == "overdue":
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
            run_coach = st.button("✨ Get Coaching Tips", type="primary", use_container_width=True)
        
        if run_coach:
            from services.gemini import analyze_team_health
            
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
                    score = dim.get("score", 0)
                    status = dim.get("status", "")
                    
                    with cols[i]:
                        st.metric(label.split(" ")[0], f"{score}%")
                        if "🟢" in status:
                            st.success(status, icon="✅")
                        elif "🔴" in status:
                            st.error(status, icon="🚨")
                        else:
                            st.warning(status, icon="⚠️")
                
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



# ============================================================================
# ADMIN PANEL
# ============================================================================

@st.dialog("👑 Admin Panel", width="large")
def render_admin_panel_dialog():
    """Admin-only panel for user management."""
    # CSS: Hide native X and make dialog strictly modal
    st.markdown("""
        <style>
        div[role="dialog"] button[aria-label="Close"] { display: none; }
        div[data-baseweb="modal-backdrop"] { display: none; }
        div[data-baseweb="modal"] { background-color: rgba(0, 0, 0, 0.5); pointer-events: none; }
        div[role="dialog"]::before { content: ""; position: absolute; top: -500vh; left: -500vw; width: 1000vw; height: 1000vh; background: transparent; z-index: -1; pointer-events: auto; }
        div[role="dialog"] { overflow: visible !important; pointer-events: auto; }
        div[role="dialog"] [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"]:last-child button { border-radius: 50%; border: 1px solid #e0e0e0; width: 35px; height: 35px; padding: 0 !important; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); background-color: white; }
        </style>
    """, unsafe_allow_html=True)
    
    # Header with Close button
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown("### User Management")
    if c_close.button("", icon=":material/close:", key="close_admin_panel"):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.rerun()
    
    # Require Admin role
    if st.session_state.get("user_role") != "admin":
        st.error("🚫 Access Denied. Admin privileges required.")
        return
    
    tab1, tab2 = st.tabs(["👥 User List", "➕ Create User"])
    
    with tab1:
        users = get_all_users()
        if not users:
            st.info("No users found.")
        else:
            for user in users:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1.5, 1, 1])
                    c1.markdown(f"**{user.display_name}** (`{user.username}`)")
                    c2.caption(f"Role: {user.role.value.title()}")
                    
                    status_color = "🟢" if user.is_active else "🔴"
                    c3.markdown(f"{status_color} {'Active' if user.is_active else 'Inactive'}")
                    
                    if user.username != "admin":  # Prevent editing the main admin
                        if c4.button("🗑️", key=f"deact_{user.id}", help="Deactivate"):
                            update_user(user.id, is_active=not user.is_active)
                            st.rerun()
    
    with tab2:
        st.markdown("#### Create New User")
        new_username = st.text_input("Username", key="new_username")
        new_display = st.text_input("Display Name", key="new_display")
        new_password = st.text_input("Password", type="password", key="new_password")
        new_role = st.selectbox("Role", options=["member", "manager", "admin"], key="new_role")
        
        # Manager assignment (for members)
        managers = [u for u in get_all_users() if u.role.value in ["manager", "admin"]]
        manager_options = {u.display_name: u.id for u in managers}
        new_manager = st.selectbox("Assigned Manager", options=["None"] + list(manager_options.keys()), key="new_manager")
        
        if st.button("Create User", type="primary"):
            if new_username and new_password:
                try:
                    manager_id = manager_options.get(new_manager) if new_manager != "None" else None
                    create_user(
                        username=new_username,
                        password=new_password,
                        role=UserRole(new_role),
                        display_name=new_display or new_username,
                        manager_id=manager_id
                    )
                    st.success(f"User '{new_username}' created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating user: {e}")
            else:
                st.error("Username and Password are required.")
    
    with st.expander("🔑 Reset Password"):
        users = get_all_users()
        user_options = {u.display_name: u.id for u in users}
        selected_user = st.selectbox("Select User", options=list(user_options.keys()), key="reset_user")
        new_pw = st.text_input("New Password", type="password", key="new_pw")
        confirm_pw = st.text_input("Confirm Password", type="password", key="confirm_pw")
        
        if st.button("Reset Password", type="primary", key="reset_pw_btn"):
            if new_pw and new_pw == confirm_pw:
                user_id = user_options.get(selected_user)
                if user_id and reset_user_password(user_id, new_pw):
                    st.success(f"Password for '{selected_user}' reset successfully!")
                else:
                    st.error("Failed to reset password.")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match.")
            else:
                st.error("Please enter a new password.")


@st.dialog("🔄 Weekly Ritual", width="large")
def render_weekly_ritual_dialog(data, username):
    st.markdown("### Weekly Check-in Ritual")
    
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle first.")
        return

    # Initialize ritual state
    if "ritual_step" not in st.session_state:
        st.session_state.ritual_step = 1
    
    step = st.session_state.ritual_step
    
    # Progress Stepper
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**1. Review Week** {'✅' if step > 1 else '🔵' if step==1 else '⚪'}")
    c2.markdown(f"**2. Update KRs** {'✅' if step > 2 else '🔵' if step==2 else '⚪'}")
    c3.markdown(f"**3. Plan Next** {'✅' if step > 3 else '🔵' if step==3 else '⚪'}")
    st.markdown("---")

    # === STEP 1: REVIEW WEEK ===
    if step == 1:
        st.markdown("#### 📅 Week in Review")
        
        # Calculate stats for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_ts = int(start_date.timestamp() * 1000)
        
        # Collect work logs
        total_minutes = 0
        completed_tasks = []
        work_logs_text = []
        
        for nid, node in data.get("nodes", {}).items():
            # Check completed tasks
            if node.get("type") == "TASK" and node.get("progress") == 100:
                # Check if completed recently (hack: use last work log or modify time)
                # For now, just listing all 100% tasks as "Achievements" if meaningful
                pass 
                
            for log in node.get("workLog", []):
                if log["startedAt"] >= start_ts:
                    mins = log.get("duration", 0) / 60
                    total_minutes += mins
                    work_logs_text.append(f"- {node.get('title')}: {log.get('summary', 'Work')} ({int(mins)}m)")
        
        # AI Summary Generation
        if "ritual_summary" not in st.session_state:
            if st.button("✨ Generate AI Summary", type="primary"):
                with st.spinner("Analyzing your week..."):
                     from services.gemini import generate_weekly_summary
                     stats = {
                         "total_minutes": total_minutes,
                         "tasks_completed": 0, # Placeholder
                         "krs_updated": 0,    # Placeholder
                         "work_logs_text": "\n".join(work_logs_text[:50]) # Limit context
                     }
                     res = generate_weekly_summary(username, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), stats)
                     if "error" not in res:
                         st.session_state.ritual_summary = res
                         st.rerun()
                     else:
                         st.error(res["error"])
        
        # Display Summary
        summary = st.session_state.get("ritual_summary")
        if summary:
            st.markdown(summary.get("summary_markdown"))
            
            st.markdown("**🏆 Highlights**")
            for h in summary.get("highlights", []):
                st.success(h)
                
            st.info(f"💡 **Focus Analysis:** {summary.get('focus_analysis')}")
        
        st.markdown(f"**Total Focus Time:** {format_time(total_minutes)} this week.")
        
        col_nav = st.columns([1, 1])
        if col_nav[1].button("Next: Update KRs ➡️", type="primary"):
            st.session_state.ritual_step = 2
            st.rerun()

    # === STEP 2: UPDATE KRs ===
    elif step == 2:
        st.markdown("#### 📊 Key Result Updates")
        needing_update = get_krs_needing_checkin(user_id=username, cycle_id=cycle_id, days_threshold=7)
        
        if not needing_update:
            st.success("🎉 All Key Results are up to date!")
        else:
            st.write(f"You have {len(needing_update)} Key Results pending update.")
            
            for i, kr in enumerate(needing_update):
                with st.expander(f"📊 {kr.title}", expanded=(i==0)):
                    st.caption(f"Current: {kr.current_value} {kr.unit or ''} | Target: {kr.target_value}")
                    
                    with st.form(f"checkin_form_{kr.id}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            new_val = st.number_input("New Value", value=float(kr.current_value), key=f"val_{kr.id}")
                        with c2:
                            conf = st.slider("Confidence (0-10)", 0, 10, 5, key=f"conf_{kr.id}")
                        
                        comment = st.text_area("What changed?", placeholder="Progress update...", key=f"comm_{kr.id}")
                        
                        if st.form_submit_button("✅ Update"):
                            create_check_in(kr.id, new_val, conf, comment)
                            # Sync JSON
                            if kr.external_id and kr.external_id in data["nodes"]:
                                n = data["nodes"][kr.external_id]
                                n["current_value"] = new_val
                                if kr.target_value > 0:
                                    n["progress"] = int((new_val / kr.target_value) * 100)
                                save_data(data, username)
                            st.toast(f"Updated {kr.title}!")
                            time.sleep(0.5)
                            st.rerun()
                            
        col_nav = st.columns([1, 1])
        if col_nav[0].button("⬅️ Back"):
            st.session_state.ritual_step = 1
            st.rerun()
        if col_nav[1].button("Next: Plan Week ➡️", type="primary"):
            st.session_state.ritual_step = 3
            st.rerun()

    # === STEP 3: PLAN NEXT WEEK ===
    elif step == 3:
        st.markdown("#### 🎯 Planning Next Week")
        
        st.write("What are your top 3 priorities for the upcoming week?")
        
        with st.form("planning_form"):
            p1 = st.text_input("Priority #1", placeholder="Top focus...")
            p2 = st.text_input("Priority #2", placeholder="Secondary focus...")
            p3 = st.text_input("Priority #3", placeholder="Tertiary focus...")
            has_deadlines = st.checkbox("Check upcoming deadlines", value=True)
            
            if st.form_submit_button("🚀 Finish Ritual"):
                st.toast("Weekly Ritual Complete! Have a great week.")
                # Could save this plan to storage if needed
                del st.session_state.ritual_step
                if "ritual_summary" in st.session_state:
                    del st.session_state.ritual_summary
                if "active_report_mode" in st.session_state:
                    del st.session_state.active_report_mode
                st.rerun()
        
        if has_deadlines:
            # Show tasks due in next 7 days
            week_from_now = (datetime.now() + timedelta(days=7)).timestamp() * 1000
            now_ts = datetime.now().timestamp() * 1000
            
            upcoming = []
            for nid, node in data.get("nodes", {}).items():
                if node.get("type") == "TASK" and node.get("deadline"):
                    d = node.get("deadline")
                    if now_ts <= d <= week_from_now and node.get("progress") < 100:
                        upcoming.append(node)
            
            if upcoming:
                st.warning(f"You have {len(upcoming)} tasks due this week:")
                for t in upcoming:
                    st.write(f"- {t.get('title')}")
        
        if st.button("⬅️ Back"):
            st.session_state.ritual_step = 2
            st.rerun()

# ============================================================================
# Main App Logic
# ============================================================================
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

    # Header with Close Button
    st.caption(f"Tasks with work recorded for: {mode} ({period_label})")
    
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
                if st.button("✨ Generate AI Weekly Brief", type="primary"):
                     with st.spinner("Drafting executive summary..."):
                         from services.gemini import generate_weekly_summary
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
                             
            summary = st.session_state.get("report_summary")
            if summary:
                st.markdown(summary.get("summary_markdown"))
                
                # Metrics Row
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Focus", format_time(total))
                m2.metric("Tasks Completed", len(achievements))
                m3.metric("Key Highlights", len(summary.get("highlights", [])))
                
                with st.expander("📌 Highlights"):
                    for h in summary.get("highlights", []):
                        st.markdown(f"- {h}")
            else:
                st.info("Click above to generate an executive brief of your week.")

    st.markdown("---")

    # === TRENDS & ANALYSIS ===
    c_trend, c_achieve = st.columns([1.5, 1])
    
    with c_trend:
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

    with c_achieve:
        st.subheader("🏆 Achievements")
        if achievements:
            for a in achievements:
                st.success(f"✅ {a}")
        else:
            st.caption("No completed tasks this period.")
            
    # Deadline Health
    st.subheader("⚠️ Deadline Health")
    # Quick scan for overdue/at risk
    warnings = []
    for nid, node in data["nodes"].items():
        if node.get("type") == "TASK" and node.get("deadline") and node.get("progress") < 100:
             from utils.deadline_utils import get_deadline_status
             _, label, _ = get_deadline_status(node)
             if "Overdue" in label or "At Risk" in label:
                 warnings.append(f"{label} - {node.get('title')}")
    
    if warnings:
        for w in warnings[:5]:
            st.error(w)
        if len(warnings) > 5:
            st.caption(f"...and {len(warnings)-5} more.")
    else:
        st.success("All tasks on track!", icon="🟢")


    # Filter Key Results (Needed for PDF)
    krs = []
    for nid, node in data["nodes"].items():
        if node.get("type") == "KEY_RESULT":
            krs.append(node)

    # PDF Export (Moved to Top)
    try:
        import importlib
        import services.pdf_report
        importlib.reload(services.pdf_report)
        from services.pdf_report import generate_weekly_pdf_v2
        
        # Generate PDF
        # Only include key_results filter for PDF if mode is Weekly
        pdf_krs = krs if mode == "Weekly" else []
        
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
                 mime="application/pdf"
             )
    except Exception as e:
        st.error(f"PDF Generation Error: {e}")

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
        for item in report_items:
            summary_text = item.get("Summary", "")
            
            table_html += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px;">{item['Task']}</td>
                     <td style="padding: 8px; color: #555;">{item['Objective']}</td>
                     <td style="padding: 8px; color: #555;">{item['KeyResult']}</td>
                    <td style="padding: 8px; white-space: nowrap;">{item['Date']} {item['Time']}</td>
                    <td style="padding: 8px; text-align: right;">{item['Duration (m)']}m</td>
                    <td style="padding: 8px; color: #555;">{summary_text}</td>
                </tr>"""
        table_html += "</tbody></table>"
        st.markdown(table_html, unsafe_allow_html=True)
    
    st.metric(f"Total Time ({period_label})", format_time(total))
    
    st.markdown("---")
    st.subheader("Time Distribution by Objective")
    
    # Prepare data for chart/table
    obj_data = []
    # Sort stats by minutes descending first
    sorted_stats = sorted(objective_stats.items(), key=lambda item: item[1], reverse=True)
    
    # Using HTML table for objectives too
    obj_table_html = """<table style="width:100%; border-collapse: collapse; font-family: 'Vazirmatn', sans-serif; font-size: 0.95em;">
        <thead>
            <tr style="border-bottom: 2px solid #ddd; background-color: #f8f9fa;">
                <th style="padding: 8px; text-align: left;">Objective</th>
                <th style="padding: 8px; text-align: right;">Time</th>
                <th style="padding: 8px; text-align: right;">%</th>
            </tr>
        </thead>
        <tbody>"""
    
    for title, mins in sorted_stats:
        percentage = (mins / total * 100) if total > 0 else 0
        p_str = f"{percentage:.1f}%"
        t_str = format_time(mins)
        
        obj_table_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 8px;">{title}</td>
                <td style="padding: 8px; text-align: right;">{t_str}</td>
                <td style="padding: 8px; text-align: right;">{p_str}</td>
            </tr>"""
    obj_table_html += "</tbody></table>"
    st.markdown(obj_table_html, unsafe_allow_html=True)


    
    # --- SECTION: Key Result Strategic Status (Weekly Only) ---
    if mode == "Weekly":
        st.markdown("---")
        st.subheader("Key Result Strategic Status")
        
        # 1. Filter Key Results (Already done above)
            
        if not krs:
            st.info("No Key Results found.")
        else:
            # Header Row
            # Header Row
            h1, h2, h3, h4, h5, h6 = st.columns([2.5, 1.2, 1.2, 1.2, 1.2, 0.8])
            h1.markdown("**Key Result**")
            h2.markdown("**Progress**", help="Calculated from child tasks")
            h3.markdown("**Efficiency**", help="Completeness of work scope vs required")
            h4.markdown("**Effectiveness**", help="Quality of strategy and methods")
            h5.markdown("**Fulfillment**", help="Overall Score")
            h6.markdown("**Action**")
            
            st.markdown("<hr style='margin: 5px 0; border: none; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
            
            from services.gemini import analyze_node

            for kr in krs:
                # Prepare Data
                title = kr.get("title", "Untitled")
                
                # Render Row Layout
                # Render Row Layout
                c1, c2, c3, c4, c5, c6 = st.columns([2.5, 1.2, 1.2, 1.2, 1.2, 0.8])
                
                c1.markdown(f"{title}")
                c2.markdown(f"{kr.get('progress', 0)}%")
                
                # Placeholders for dynamic updates
                p_eff = c3.empty()
                p_qual = c4.empty()
                p_full = c5.empty()
                
                # Action Button
                do_update = c6.button("🔄", key=f"upd_kr_{kr['id']}", help="Update Analysis")
                
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
                render_kr_state(kr)
            
            # Handle Update
            if do_update:
                with st.spinner("Analyzing..."):
                    from utils.storage import filter_nodes_by_cycle
                    cycle_id = st.session_state.get("active_cycle_id")
                    filtered_nodes = filter_nodes_by_cycle(data["nodes"], cycle_id)
                    res = analyze_node(kr['id'], filtered_nodes)
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        # Update Data
                        update_node(data, kr['id'], {"geminiAnalysis": res}, username)
                        # Update UI immediately via placeholders (No Rerun)
                        kr["geminiAnalysis"] = res # Update local var for rendering
                        render_kr_state(kr)

@st.dialog("Work Report", width="large")
def render_report_dialog(data, username, mode="Weekly"):
    render_report_content(data, username, mode)

@st.dialog("Inspect & Edit", width="large")
def render_inspector_dialog(node_id, data, username):
    render_inspector_content(node_id, data, username)

@st.fragment
def render_inspector_content(node_id, data, username):
    # CSS: Hide native X and style YOUR EXISTING custom button as a circle
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

        /* 3. The Visual Background Layer 
           - We use the modal container to paint the black screen.
           - We set pointer-events: none so clicks pass through it (bypassing Streamlit's close listener on this element).
        */
        div[data-baseweb="modal"] {
            background-color: rgba(0, 0, 0, 0.5);
            pointer-events: none; /* Look but don't touch */
        }

        /* 4. The "Invisible Click Shield" 
           - We attach a massive invisible layer to the Dialog Box itself.
           - We use huge negative margins to make it cover the whole screen.
           - Because it is a child of "dialog", clicking it reports the target as "dialog", so Streamlit does NOT close.
           - We set pointer-events: auto to CATCH the click so it doesn't fall through to the app.
        */
        div[role="dialog"]::before {
            content: "";
            position: absolute;
            top: -500vh;
            left: -500vw;
            width: 1000vw;
            height: 1000vh;
            background: transparent; /* Invisible */
            z-index: -1;             /* Behind the dialog content */
            cursor: default;
            pointer-events: auto;    /* Catch the click! */
        }

        /* 5. Ensure the Dialog Box is Interactive */
        div[role="dialog"] {
            overflow: visible !important; /* Allow the shield to extend outside */
            pointer-events: auto;         /* Re-enable clicking inside the box */
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

    title = node.get('title', 'Untitled')
    progress = node.get('progress', 0)
    node_type = node.get('type', 'GOAL')
    has_children = len(node.get("children", [])) > 0
    
    node_type = node.get('type', 'GOAL')
    has_children = len(node.get("children", [])) > 0
    
    # Header logic with Close
    c_head, c_close = st.columns([0.92, 0.08])
    c_head.markdown(f"### {TYPE_ICONS.get(node_type, '')} {title}")
    if c_close.button("", icon=":material/close:", key=f"close_insp_{node_id}"):
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()
    
    with st.form(key=f"edit_{node_id}"):
        new_title = st.text_input("Title", value=title)
        new_desc = st.text_area("Description", value=node.get("description", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            p_prog_container = st.empty()
            if has_children:
                 p_prog_container.metric("Progress (Calculated)", value=f"{progress}%")
                 new_progress = progress 
            else:
                 new_progress = p_prog_container.slider("Progress (Manual)", 0, 100, value=progress)
        
        with col2:
            current_index = TYPES.index(node_type) if node_type in TYPES else 0
            new_type = st.selectbox("Type", TYPES, index=current_index)
            
        # GOAL Specific Cycle Assignment
        new_cycle_id = node.get("cycle_id")
        if node_type == "GOAL":
            st.markdown("---")
            st.caption("📅 Cycle Assignment")
            from src.crud import get_all_cycles
            all_cycles = get_all_cycles()
            cycle_titles = [c.title for c in all_cycles]
            cycle_ids = [c.id for c in all_cycles]
            
            try:
                current_cyc_idx = cycle_ids.index(new_cycle_id)
            except:
                current_cyc_idx = 0
                
            selected_cyc_title = st.selectbox("Assign to Cycle", options=cycle_titles, index=current_cyc_idx, key=f"cyc_assign_{node_id}")
            new_cycle_id = all_cycles[cycle_titles.index(selected_cyc_title)].id
            
            # Strategy Tags (free-text multi-select)
            st.caption("♟️ Strategy Tags")
            current_strat_tags = node.get("strategy_tags", [])
            new_strat_tags_input = st.text_input("Add Strategy Tags (comma-separated)", value=", ".join(current_strat_tags), key=f"strat_tags_{node_id}")

        # KEY_RESULT Specific Metrics
        new_target = node.get("target_value", 100.0)
        new_current = node.get("current_value", 0.0)
        new_unit = node.get("unit", "%")
        
        if node_type == "KEY_RESULT":
            st.markdown("---")
            st.caption("📈 Progress Metrics")
            mc1, mc2, mc3 = st.columns(3)
            new_target = mc1.number_input("Target Value", value=float(new_target), key=f"target_{node_id}")
            new_current = mc2.number_input("Current Value", value=float(new_current), key=f"curr_{node_id}")
            new_unit = mc3.text_input("Unit", value=new_unit, key=f"unit_{node_id}")
            
            # Recalculate progress if using metrics
            if new_target > 0:
                calc_prog = int((new_current / new_target) * 100)
                calc_prog = max(0, min(100, calc_prog))
                if not has_children:
                    new_progress = calc_prog
                    st.info(f"Calculated Progress: {new_progress}%")
            
            # Initiative Tags (free-text multi-select)
            st.caption("⚡ Initiative Tags")
            current_init_tags = node.get("initiative_tags", [])
            new_init_tags_input = st.text_input("Add Initiative Tags (comma-separated)", value=", ".join(current_init_tags), key=f"init_tags_{node_id}")

        # Permission Check for Save
        node_owner = node.get("user_id")
        can_save = (username == node_owner)
        
        if st.form_submit_button("💾 Save Changes", disabled=not can_save):
            # Parse tags
            new_strat_tags = [t.strip() for t in new_strat_tags_input.split(",") if t.strip()] if node_type == "GOAL" else node.get("strategy_tags", [])
            new_init_tags = [t.strip() for t in new_init_tags_input.split(",") if t.strip()] if node_type == "KEY_RESULT" else node.get("initiative_tags", [])
            
            update_node(data, node_id, {
                "title": new_title,
                "description": new_desc,
                "progress": new_progress,
                "type": new_type,
                "target_value": new_target,
                "current_value": new_current,
                "unit": new_unit,
                "cycle_id": new_cycle_id,
                "strategy_tags": new_strat_tags,
                "initiative_tags": new_init_tags
            }, username)
            st.rerun()

    # Time Tracking (Tasks only - Initiative is now a tag)
    if node_type == "TASK":
        st.markdown("---")
        st.write("### ⏱️ Time Tracking")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
             user_role = st.session_state.get("user_role", "member")
             is_running = node.get("timerStartedAt") is not None
             
             if is_running:
                  start_ts = node.get("timerStartedAt")
                  elapsed = int((time.time() * 1000 - start_ts) / 60000)
                  st.info(f"Timer Running: {elapsed}m")
                  
             if user_role == "member":
                 if is_running:
                      c_act1, c_act2 = st.columns(2)
                      if c_act1.button("Open Timer", icon=":material/timer:"):
                          st.session_state.active_timer_node_id = node_id
                          if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                          st.rerun()
                      if c_act2.button("Stop", icon=":material/stop_circle:"):
                          stop_timer(data, node_id, username)
                          if "active_timer_node_id" in st.session_state:
                              del st.session_state.active_timer_node_id
                          st.rerun()
                 else:
                      if st.button("Start Timer", icon=":material/play_circle:"):
                          start_timer(data, node_id, username)
                          st.session_state.active_timer_node_id = node_id
                          if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                          st.rerun()
             else:
                 st.caption("🕒 Timers are reserved for Members.")
        
        with col_t2:
            total = get_total_time(node_id, data["nodes"])
            st.metric("Total Time", format_time(total))

    # Deadline (Tasks only)
    if node_type == "TASK":
        st.markdown("---")
        st.write("### 📅 Deadline")
        
        from utils.deadline_utils import get_deadline_status, get_days_remaining, format_deadline_display
        
        current_deadline = node.get("deadline")
        current_date = datetime.fromtimestamp(current_deadline / 1000).date() if current_deadline else None
        
        col_d1, col_d2 = st.columns([2, 1])
        with col_d1:
            new_deadline_date = st.date_input(
                "Due Date",
                value=current_date,
                key=f"deadline_{node_id}"
            )
            
            # Convert date to timestamp if changed
            if new_deadline_date:
                new_deadline_ts = int(datetime.combine(new_deadline_date, datetime.max.time()).timestamp() * 1000)
            else:
                new_deadline_ts = None
            
            # Save button for deadline
            btn_col1, btn_col2 = st.columns(2)
            if btn_col1.button("💾 Save Deadline", key=f"save_deadline_{node_id}"):
                update_node(data, node_id, {"deadline": new_deadline_ts}, username)
                st.toast("Deadline saved!")
                st.rerun()
            if current_deadline and btn_col2.button("🗑️ Clear", key=f"clear_deadline_{node_id}"):
                update_node(data, node_id, {"deadline": None}, username)
                st.toast("Deadline cleared!")
                st.rerun()
                
        with col_d2:
            if current_deadline:
                status_code, status_label, health = get_deadline_status(node)
                days = get_days_remaining(current_deadline)
                
                st.metric("Status", status_label)
                if days >= 0:
                    st.caption(f"📆 {days} days remaining")
                else:
                    st.caption(f"⚠️ {abs(days)} days overdue")
                st.progress(health / 100, text=f"Health: {health}%")
            else:
                st.info("No deadline set")

     # Work History (Tasks)

    if node_type == "TASK":
         st.markdown("---")
         st.markdown("### 📜 Work History")
         work_log = node.get("workLog", [])
         if work_log:
             # Sort by date desc
             work_log_sorted = sorted(work_log, key=lambda x: x.get("endedAt", 0), reverse=True)
             
             # Header
             c1, c2, c3, c4 = st.columns([2, 1, 3, 0.5])
             c1.markdown("**Date**")
             c2.markdown("**Duration**")
             c3.markdown("**Summary**")
             
             for log in work_log_sorted:
                 date_str = datetime.fromtimestamp(log.get("endedAt", 0)/1000).strftime('%Y-%m-%d %H:%M')
                 dur = f"{round(log.get('durationMinutes', 0), 1)}m"
                 summ = log.get("summary", "") or "-"
                 started_at = log.get("startedAt")
                 
                 c1, c2, c3, c4 = st.columns([2, 1, 3, 0.5])
                 c1.markdown(date_str)
                 c2.markdown(dur)
                 c3.markdown(f"<span style='color: #666'>{summ}</span>", unsafe_allow_html=True)
                 
                 if c4.button("🗑️", key=f"del_log_{node_id}_{started_at}", help="Delete this entry", type="tertiary"):
                     delete_work_log(data, node_id, started_at, username)
                     st.rerun()
         else:
             st.info("No work recorded yet.")

    # AI Analysis (Key Result)
    if node_type == "KEY_RESULT":
        from services.gemini import analyze_node
        st.markdown("---")
        st.markdown("### 🧠 AI Strategic Analysis")
        
        if st.button("✨ Run Analysis", type="primary"):
             with st.spinner("Consulting Gemini Strategy Agent..."):
                 from utils.storage import filter_nodes_by_cycle
                 cycle_id = st.session_state.get("active_cycle_id")
                 filtered_nodes = filter_nodes_by_cycle(data["nodes"], cycle_id)
                 res = analyze_node(node_id, filtered_nodes)
                 if "error" in res: st.error(res["error"])
                 else:
                     # Flatten result into node for storage
                     update_node(data, node_id, {
                         "geminiAnalysis": res["analysis"], # Store the result
                         "geminiLastSnapshot": res["snapshot"] # Store the snapshot
                     }, username)
                     
                     # Update local node object for immediate rendering
                     node["geminiAnalysis"] = res["analysis"]
                     node["geminiLastSnapshot"] = res["snapshot"]
        
        analysis = node.get("geminiAnalysis")
        if analysis and isinstance(analysis, dict):
            # Display new format
            st.markdown("#### Scorecard")
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Efficiency", f"{analysis.get('efficiency_score', 0)}%", help="Completeness of work scope vs required")
            col_s2.metric("Effectiveness", f"{analysis.get('effectiveness_score', 0)}%", help="Quality of strategy and methods")
            col_s3.metric("Overall", f"{analysis.get('overall_score', 0)}%")
            
            st.info(f"**Executive Summary:** {analysis.get('summary', 'N/A')}")
            
            with st.expander("Gap Analysis & Quality assessment", expanded=True):
                st.markdown(f"**Gap Analysis:**\n{analysis.get('gap_analysis', 'N/A')}")
                st.markdown(f"**Quality Assessment:**\n{analysis.get('quality_assessment', 'N/A')}")
            
            # Display deadline warnings if any
            deadline_warnings = analysis.get("deadline_warnings", [])
            if deadline_warnings:
                st.markdown("#### ⚠️ Deadline Warnings")
                for warning in deadline_warnings:
                    st.warning(warning)
            
            if analysis.get("proposed_tasks"):

                st.markdown("#### 🚀 Proposed Missing Tasks")
                for task in analysis["proposed_tasks"]:
                    c1, c2 = st.columns([0.8, 0.2])
                    c1.markdown(f"- {task}")
                    if c2.button("Add", key=f"add_prop_{task[:10]}_{node_id}"):
                         # Add Task directly under Key Result
                         add_node(data, node_id, "TASK", task, "AI Proposed Task", username)
                         st.toast(f"Added task: {task}")
                         st.rerun()

        elif analysis and isinstance(analysis, str):
             # Legacy content fallback
             st.info(analysis)

    st.markdown("---")
    
    # Permission Check: Only owner can delete
    node_owner = node.get("user_id")
    if username == node_owner:
        if st.button("🗑️ Delete Entity", type="primary"):
            delete_node(data, node_id, username)
            st.rerun()
    else:
        role_label = st.session_state.get("user_role", "member").title()
        st.info(f"ℹ️ {role_label}s have read-only access to member OKRs.")


def render_card(node_id, data, username):
    node = data["nodes"].get(node_id)
    if not node: return

    title = node.get("title", "Untitled")
    progress = node.get("progress", 0)
    node_type = node.get("type", "GOAL")
    children_names = [data["nodes"][c]["title"] for c in node.get("children", []) if c in data["nodes"]]
    has_children = len(node.get("children", [])) > 0
    is_leaf = node_type == "TASK" # Tasks don't have navigable children in our map
    
    # CSS Frame
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        with c1:
            # Clickable Title => Navigate
            # Using a button that looks like title.
            label = f"{TYPE_ICONS.get(node_type, '')} {title}"
            
            # Subtitle stats
            stats = f"📊 {progress}% | {node_type.replace('_',' ').title()}"
            if node_type == "TASK":
                t = get_total_time(node_id, data["nodes"])
                stats += f" | ⏱️ {format_time(t)}"
                # Add deadline indicator
                if node.get("deadline"):
                    from utils.deadline_utils import get_deadline_status, format_deadline_display
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
            creator_name = node.get("created_by_display_name") or node.get("user_id") or "Unknown"
            tags_row_html += f"<span style='background-color:#F5F5F5;color:#616161;padding:2px 8px;border-radius:10px;font-size:0.75em;margin-right:4px;border:1px solid #e0e0e0;'>✍️ {creator_name}</span>"
            
            # 👤 Owner Tag (Goals only, for Admin/Manager viewing team)
            if user_role in ["admin", "manager"] and node_type == "GOAL":
                owner_name = node.get("owner_display_name") or node.get("user_id", "Unknown")
                tags_row_html += f"<span style='background-color:#E3F2FD;color:#1565C0;padding:2px 8px;border-radius:10px;font-size:0.75em;'>👤 {owner_name}</span>"
            
            if tags_row_html:
                st.markdown(f"<div style='margin-top:4px;'>{tags_row_html}</div>", unsafe_allow_html=True)
            
            # --- SELF HEALING: Check hierarchy mismatch ---
            parent_id = node.get("parentId")
            if parent_id:
                parent = data["nodes"].get(parent_id)
                if parent:
                    # Expected type based on parent
                    parent_type = parent.get("type", "").upper()
                    expected_child_type = CHILD_TYPE_MAP.get(parent_type)
                    
                    # If expected type exists, is different from current, AND current is 'TASK' (common error)
                    # or generally mismatch.
                    if expected_child_type and node_type != expected_child_type:
                        # Case: KeyResult (expects Initiative) -> Has Task
                        # Show Fix Button - User friendly label
                        # If expected is INITIATIVE, child of expected is TASK.
                        if expected_child_type == "INITIATIVE":
                            action_label = "➡️ Enable Tasks Level"
                        else:
                            action_label = f"🔧 Fix Type (to {expected_child_type.replace('_',' ').title()})"
                        
                        if st.button(action_label, key=f"fix_{node_id}", help="Click to fix the hierarchy and enable drill-down"):
                            update_node(data, node_id, {"type": expected_child_type}, username)
                            st.rerun()

        with c2:
             # Timer Controls (If Task)
             if node_type == "TASK":
                 is_running = node.get("timerStartedAt") is not None
                 if is_running:
                     start_ts = node.get("timerStartedAt", 0)
                     elapsed = int((time.time() * 1000 - start_ts) / 60000)
                     if st.button(f"Running ({elapsed}m)", icon=":material/timer:", key=f"open_timer_{node_id}", help="Click to view timer"):
                         st.session_state.active_timer_node_id = node_id
                         if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                         st.rerun()
                 else:
                     if st.button("Start Timer", icon=":material/play_arrow:", key=f"start_card_{node_id}", help="Start Timer"):
                         start_timer(data, node_id, username)
                         st.session_state.active_timer_node_id = node_id
                         if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
                         st.rerun()
             
             if st.button("Inspect", icon=":material/search:", key=f"inspect_{node_id}", help="Inspect & Edit"):
                 st.session_state.active_inspector_id = node_id
                 if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
                 st.rerun()
             
             # View Map button - only show if node has children
             if has_children:
                 if st.button("Map", icon=":material/account_tree:", key=f"map_{node_id}", help="View Mind Map"):
                      render_mindmap_dialog(node_id, data)
                 
        with c3:
            # Navigation Button ("Open")
            if not is_leaf:
                if st.button("Open", icon=":material/arrow_forward:", key=f"nav_{node_id}", help="Drill Down"):
                    navigate_to(node_id)
            
            # AI Analysis Quick Button
            if node_type == "KEY_RESULT":
                if st.button("AI", icon=":material/psychology:", key=f"ai_card_{node_id}", help="Run Quick AI Strategic Analysis"):
                    from services.gemini import analyze_node
                    from utils.storage import filter_nodes_by_cycle
                    cycle_id = st.session_state.get("active_cycle_id")
                    filtered_nodes = filter_nodes_by_cycle(data["nodes"], cycle_id)
                    with st.spinner("🧠 Gemini is auditing..."):
                        res = analyze_node(node_id, filtered_nodes)
                        if "error" in res:
                            st.error(res["error"])
                        else:
                            update_node(data, node_id, {
                                "geminiAnalysis": res["analysis"],
                                "geminiLastSnapshot": res["snapshot"]
                            }, username)
                            st.toast(f"✅ AI Analysis complete for: {title}")
                            st.rerun()
            elif node_type == "TASK":
                 # Maybe show something else? or Empty?
                 pass

def render_level(data, username, root_ids=None):
    stack = st.session_state.nav_stack
    
    # Determine what to show
    if not stack:
        # Root Level
        items = root_ids if root_ids is not None else data.get("rootIds", [])
        level_name = "Goals"
        current_node = None
    else:
        # Child Level
        parent_id = stack[-1]
        current_node = data["nodes"].get(parent_id)
        if not current_node:
            st.error("Node not found")
            st.session_state.nav_stack.pop() # Recovery
            st.rerun()
            return
            
        items = current_node.get("children", [])
        # Determine label
        ptype = current_node.get("type")
        # Ensure ptype is valid key (handle potential fallback/legacy data)
        ctype = CHILD_TYPE_MAP.get(ptype)
        
        if not ctype:
             # Try to guess from children if any exist
             if items:
                 first = data["nodes"].get(items[0])
                 if first:
                     ctype = first.get("type")
        
        if ctype:
             normalized = ctype.replace('_',' ').title()
             if normalized.endswith('y'):
                 level_name = normalized[:-1] + "ies"
             elif normalized.endswith('s'):
                 level_name = normalized
             else:
                 level_name = f"{normalized}s"
        else:
             level_name = "Items"

    # Header
    render_breadcrumbs(data)
    
    if current_node:
        # User wants "TYPE" as top title. e.g. "Strategies"
        st.markdown(f"## {level_name}")
        # Removing caption as requested
        # st.caption(f"Inside: {current_node.get('title')}")
        
        # Add New Button logic
        # Robust lookup: ensure upper case
        current_type = current_node.get("type", "").upper()
        child_type = CHILD_TYPE_MAP.get(current_type)
        
        if child_type:
             # Specialized Permissions:
             # - Admins/Managers can add any sub-item (Obj, KR, Task) to nodes they see.
             # - Members can ONLY add Tasks to their own nodes.
             user_role = st.session_state.get("user_role", "member")
             node_owner = current_node.get("user_id")
             is_owner = (username == node_owner)
             
             can_add = False
             if user_role in ["admin", "manager"]:
                 can_add = True
             elif user_role == "member":
                 if child_type == "TASK" and is_owner:
                     can_add = True
             
             if can_add:
                 normalized_btn = child_type.replace('_',' ').title()
                 if st.button(f"➕ New {normalized_btn}", key=f"add_btn_{current_node['id']}"):
                     add_node(data, current_node["id"], child_type, f"New {normalized_btn}", "", username, cycle_id=st.session_state.active_cycle_id)
                     st.rerun()
    else:
        st.markdown(f"## {level_name}")
        # Only Admins/Managers can create top-level Goals
        user_role = st.session_state.get("user_role", "member")
        if user_role in ["admin", "manager"]:
            if st.button("➕ New Goal"):
                 add_node(data, None, "GOAL", "New Goal", "", username, cycle_id=st.session_state.active_cycle_id)
                 st.rerun()

    st.markdown("---")
    
    if not items:
        st.info("No items here yet.")
    
    # List View: Expanded cards for better readability and space usage
    for item_id in items:
        render_card(item_id, data, username)


def render_app(username):
    # Sidebar Header
    display_name = st.session_state.get("display_name", username)
    user_role = st.session_state.get("user_role", "member")
    
    st.sidebar.markdown(f"👤 **{display_name}** ({user_role.title()})")
    if st.sidebar.button("🚪 Logout"):
        # Clear all user-related session state
        for key in ["user_id", "username", "display_name", "user_role", "nav_stack", 
                    "active_cycle_id", "active_report_mode", "active_timer_node_id", "active_inspector_id"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    # Admin Panel Button (Admin only)
    if st.session_state.get("user_role") == "admin":
        if st.sidebar.button("👑 Admin Panel", use_container_width=True):
            st.session_state.active_report_mode = "Admin"
            st.rerun()
    
    st.sidebar.markdown("---")
    
    init_database()
    cycles = get_all_cycles()
    
    # If no cycles exist, create a default one
    if not cycles:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        default_cycle = create_cycle(
            title="Q1 2026",
            start_date=now,
            end_date=now + timedelta(days=90),
            is_active=True
        )
        cycles = [default_cycle]
    
    # Cycle Selection in Sidebar
    st.sidebar.markdown("### 📅 OKR Cycle")
    cycle_titles = [c.title for c in cycles]
    
    # Store selected cycle in session state
    if "active_cycle_id" not in st.session_state:
        # Default to first active cycle or just the first one
        st.session_state.active_cycle_id = cycles[0].id
        
    current_cycle_index = 0
    for i, c in enumerate(cycles):
        if c.id == st.session_state.active_cycle_id:
            current_cycle_index = i
            break
            
    selected_cycle_title = st.sidebar.selectbox(
        "Select Cycle", 
        options=cycle_titles, 
        index=current_cycle_index,
        label_visibility="collapsed"
    )
    
    if st.sidebar.button("⚙️ Manage Cycles", key="manage_cycles_sidebar"):
        render_manage_cycles_dialog()
    
    # Update active_cycle_id if changed
    selected_cycle = next(c for c in cycles if c.title == selected_cycle_title)
    if selected_cycle.id != st.session_state.active_cycle_id:
        st.session_state.active_cycle_id = selected_cycle.id
        st.rerun()

    st.sidebar.markdown("---")
    
    # Navigation & Views
    st.sidebar.markdown("### 🧭 Navigation")
    if st.sidebar.button("🏠 Home / OKRs", use_container_width=True):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.session_state.nav_stack = []
        st.rerun()
        
    st.sidebar.markdown("### 📈 Insights & Reports")

    # Load data based on role
    if user_role == "admin":
        data = load_all_data()
    elif user_role == "manager":
        data = load_team_data(st.session_state.user_id)
    else:
        data = load_data(username)
    
    # Filter nodes by cycle_id
    # Note: Only Goals have cycle_id. The rest are children.
    # We should filter rootIds to only show Goals belonging to this cycle.
    # However, currently load_data returns a 'data' dict with 'nodes' and 'rootIds'.
    # We need to filter 'rootIds'.
    
    # But wait, does 'data' contain the cycle_id? The JSON might not.
    # If we are using the JSON file, it doesn't have cycle_id yet.
    # This is the "Migration Gap". 
    
    # For Phase 1 implementation, I will treat rootIds that have NO cycle_id as "Unassigned" 
    # or just show them in the first cycle.
    # Better: Update storage.py to handle cycle_id or just proceed with UI.
    
    # --- Recovery & Cleanup Logic ---
    # Ensure all GOAL nodes are in rootIds (fixes a bug where they might have been dropped during filtering)
    existing_root_ids = set(data.get("rootIds", []))
    repaired = False
    for node_id, node in data.get("nodes", {}).items():
        if node.get("type") == "GOAL" and node_id not in existing_root_ids:
            data.setdefault("rootIds", []).append(node_id)
            existing_root_ids.add(node_id)
            repaired = True
            
    # Legacy handling: Assign nodes with no cycle_id to the oldest cycle (ordered by date desc)
    oldest_cycle_id = cycles[-1].id if cycles else None
    legacy_found = False
    
    for rid in data.get("rootIds", []):
        node = data["nodes"].get(rid)
        if node:
            node_cycle_id = node.get("cycle_id")
            if node_cycle_id is None and oldest_cycle_id:
                node["cycle_id"] = oldest_cycle_id
                legacy_found = True

    # Persist if we fixed structure or legacy nodes
    if legacy_found or repaired:
        save_data(data, username)
        
    # Apply rendering filter (NON-DESTRUCTIVE - used for UI only)
    display_root_ids = []
    for rid in data.get("rootIds", []):
        node = data["nodes"].get(rid)
        if node and node.get("cycle_id") == st.session_state.active_cycle_id:
            display_root_ids.append(rid)
            
    # Use display_root_ids for the rest of the app, do NOT overwrite data["rootIds"]
    
    dialog_active = False

    if st.sidebar.button("📊 Weekly Report", use_container_width=True):
        st.session_state.active_report_mode = "Weekly"
        # Clear others
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()
        
    if st.sidebar.button("📅 Daily Report", use_container_width=True):
        st.session_state.active_report_mode = "Daily"
        # Clear others
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("🔄 Weekly Ritual", help="Guided check-in for your metrics", use_container_width=True):
        st.session_state.active_report_mode = "Ritual"
        if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("🧭 Strategic \nDashboard", help="Executive visibility", use_container_width=True):
         st.session_state.active_report_mode = "Dashboard"
         if "active_timer_node_id" in st.session_state: del st.session_state.active_timer_node_id
         if "active_inspector_id" in st.session_state: del st.session_state.active_inspector_id
         st.rerun()
    
    # Sidebar Utilities (Export)
    with st.sidebar.expander("Storage & Sync"):
        c1, c2 = st.columns(2)
        export_json = export_data(username)
        c1.download_button("Export JSON", export_json, "backup.json")
        
        if c2.button("🔄 Sync SQL", help="Force sync JSON data to Strategic Dashboard"):
            with st.spinner("Syncing..."):
                save_data(data, username)
                st.success("Successfully synchronized JSON to SQL Database!")
                st.rerun()

        uploaded = st.file_uploader("Import", type=["json"])
        if uploaded and st.button("Import Data"):
            import_data(uploaded.read().decode(), username)
            st.rerun()

    # Sync Status
    from utils.storage import get_sync_status
    is_connected, error_msg = get_sync_status()
    
    st.sidebar.markdown("---")
    if is_connected:
        st.sidebar.success("✅ Cloud Sync Active")
    else:
        st.sidebar.warning("⚠️ Local Storage Only")
        if error_msg:
             with st.sidebar.expander("Sync Error Details"):
                 st.error(error_msg)
                 st.caption("Add 'gcp_service_account' to secrets.toml")

    render_level(data, username, root_ids=display_root_ids)

    # Persistent Dialog Checks - Only if no other dialog is active
    # (Though Sidebar buttons act as triggers, if we use them to set state, we fall through here)
    if not dialog_active:
        if "active_timer_node_id" in st.session_state:
            render_timer_dialog(st.session_state.active_timer_node_id, data, username)
        elif "active_inspector_id" in st.session_state:
            render_inspector_dialog(st.session_state.active_inspector_id, data, username)
        elif "active_report_mode" in st.session_state:
            mode = st.session_state.active_report_mode
            if mode == "Ritual":
                render_weekly_ritual_dialog(data, username)
            elif mode == "Dashboard":
                render_leadership_dashboard_dialog(username)
            elif mode == "Admin":
                render_admin_panel_dialog()
            else:
                render_report_dialog(data, username, mode=mode)

def main():
    init_database() # Ensure tables exist
    ensure_admin_exists() # Create default admin if no users
    
    if "user_id" not in st.session_state:
        render_login()
    else:
        render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
