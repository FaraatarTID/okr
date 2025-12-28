import streamlit as st
import sys
import os
import time
from datetime import datetime

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, save_data, add_node, delete_node, update_node, update_node_progress, export_data, import_data, start_timer, stop_timer, get_total_time, delete_work_log
from utils.styles import apply_custom_fonts
from src.database import init_database
from src.crud import (
    get_all_cycles, create_cycle, get_active_cycles,
    create_check_in, get_krs_needing_checkin, get_check_ins,
    get_leadership_metrics, update_cycle, delete_cycle
)
import plotly.graph_objects as go
import pandas as pd

# Import streamlit-agraph for mind map visualization
from streamlit_agraph import agraph, Node, Edge, Config

st.set_page_config(page_title="OKR Tracker", layout="wide")
apply_custom_fonts()

# Full hierarchy types
TYPES = ["GOAL", "STRATEGY", "OBJECTIVE", "KEY_RESULT", "INITIATIVE", "TASK"]

CHILD_TYPE_MAP = {
    "GOAL": "STRATEGY",
    "STRATEGY": "OBJECTIVE", 
    "OBJECTIVE": "KEY_RESULT",
    "KEY_RESULT": "INITIATIVE",
    "INITIATIVE": "TASK",
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
    st.info("👋 Welcome! Please enter your **Account Name** to access your data.")
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Account Name (Unique ID)", placeholder="e.g. john_doe")
        if st.button("Enter", type="primary"):
            if username.strip():
                st.session_state["username"] = username.strip()
                st.rerun()
            else:
                st.error("Please enter a valid name.")

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
        
    metrics = get_leadership_metrics(username, cycle_id)
    if not metrics or not metrics["total_krs"]:
        st.info("No Key Results found in this cycle. Start adding goals to see insights.")
        return
        
    # --- Scorecard ---
    col1, col2, col3 = st.columns(3)
    
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
        
    st.markdown("---")
    
    # --- Plotly Heatmap ---
    st.subheader("📊 Strategic Alignment Matrix")
    
    data = metrics["heatmap_data"]
    if data:
        df = pd.DataFrame(data)
        
        # Color mapping based on confidence
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
                colorscale='RdYlGn', # Red to Green
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
        fig.add_annotation(x=90, y=10, text="⚠️ Busy Work", showarrow=False, font=dict(color="orange")) # High eff, low effect
        fig.add_annotation(x=10, y=90, text="🤔 Strategy Gap", showarrow=False, font=dict(color="blue")) # Low eff, high effect
        fig.add_annotation(x=10, y=10, text="❌ Disconnected", showarrow=False, font=dict(color="red"))

        fig.update_layout(
            xaxis_title="Efficiency (Execution Quality)",
            yaxis_title="Effectiveness (Strategy Fit)",
            xaxis=dict(range=[0, 105]),
            yaxis=dict(range=[0, 105]),
            height=600,
            template="simple_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough AI analysis data yet. Updates trigger automatic auditing.")

    # --- At Risk List ---
    if metrics["at_risk"]:
        st.markdown("### 🚨 At-Risk Key Results")
        for item in metrics["at_risk"]:
            st.error(f"**{item['title']}** — Reason: {item['reason']} (Conf: {item['confidence']})")


@st.dialog("🔄 Weekly Ritual", width="large")
def render_weekly_ritual_dialog(data, username):
    st.markdown("### Weekly Check-in")
    st.write("Review your Key Results and update their progress.")
    
    cycle_id = st.session_state.get("active_cycle_id")
    if not cycle_id:
        st.warning("Please select a cycle first.")
        return

    needing_update = get_krs_needing_checkin(user_id=username, cycle_id=cycle_id, days_threshold=7)
    
    if not needing_update:
        st.success("🎉 You are all caught up! No Key Results need a check-in right now.")
        if st.button("Close"):
             del st.session_state.active_report_mode
             st.rerun()
        return
        
    st.progress(0, f"Pending updates: {len(needing_update)}")
    
    for i, kr in enumerate(needing_update):
        with st.expander(f"📊 {kr.title}", expanded=(i==0)):
            st.caption(f"Current Value: {kr.current_value} {kr.unit or ''} | Target: {kr.target_value}")
            
            with st.form(f"checkin_form_{kr.id}"):
                c1, c2 = st.columns(2)
                with c1:
                    new_val = st.number_input("New Value", value=float(kr.current_value), key=f"val_{kr.id}")
                with c2:
                    conf = st.slider("Confidence Score (0-10)", 0, 10, 5, key=f"conf_{kr.id}")
                
                comment = st.text_area("What changed this week?", placeholder="Progress update...", key=f"comm_{kr.id}")
                
                if st.form_submit_button("✅ Submit Update"):
                    create_check_in(kr.id, new_val, conf, comment)
                    
                    # Sync back to JSON for UI consistency
                    if kr.external_id and kr.external_id in data["nodes"]:
                        json_node = data["nodes"][kr.external_id]
                        json_node["current_value"] = new_val
                        if kr.target_value > 0:
                            json_node["progress"] = int((new_val / kr.target_value) * 100)
                        save_data(data, username)
                        
                    st.toast(f"Updated {kr.title}!")
                    time.sleep(1)
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
    
    # Iterate all nodes
    for nid, node in data["nodes"].items():
        logs = node.get("workLog", [])
        if not logs: continue
        
        for log in logs:
            # Check if log is within range
            if log.get("endedAt", 0) >= start_time:
                duration = log.get("durationMinutes", 0)
                # Aggregate by Objective
                obj_title = get_ancestor_objective(nid, data["nodes"])
                kr_title = get_ancestor_key_result(nid, data["nodes"])
                
                report_items.append({
                    "Task": node.get("title", "Untitled"),
                    "Type": node.get("type", "TASK"),
                    "Date": datetime.fromtimestamp(log.get("endedAt", 0)/1000).strftime('%Y-%m-%d'),
                    "Time": datetime.fromtimestamp(log.get("endedAt", 0)/1000).strftime('%H:%M'),
                    "Duration (m)": round(duration, 2),
                    "Summary": log.get("summary", ""), # Capture summary
                    "Objective": obj_title,
                    "KeyResult": kr_title
                })
                
                objective_stats[obj_title] = objective_stats.get(obj_title, 0) + duration
    
    if not report_items:
        st.info("No work recorded in the last week.")
        return

    
    total = sum(item["Duration (m)"] for item in report_items)

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
        
        pdf_buffer = generate_weekly_pdf_v2(report_items, objective_stats, format_time(total), pdf_krs, st.session_state.report_direction, title=pdf_title, time_label=period_label)
        
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
    st.subheader("Work Log")

    # Sort items for display
    report_items.sort(key=lambda x: x["Date"] + x["Time"], reverse=True)
    
    # st.dataframe(report_items, use_container_width=True)
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
                    res = analyze_node(kr['id'], data["nodes"])
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

        if st.form_submit_button("💾 Save Changes"):
            update_node(data, node_id, {
                "title": new_title,
                "description": new_desc,
                "progress": new_progress,
                "type": new_type,
                "target_value": new_target,
                "current_value": new_current,
                "unit": new_unit,
                "cycle_id": new_cycle_id
            }, username)
            st.rerun()

    # Time Tracking (Tasks & Initiatives)
    if node_type in ["INITIATIVE", "TASK"]:
        st.markdown("---")
        st.write("### ⏱️ Time Tracking")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
             if node_type == "TASK":
                is_running = node.get("timerStartedAt") is not None
                if is_running:
                     start_ts = node.get("timerStartedAt")
                     elapsed = int((time.time() * 1000 - start_ts) / 60000)
                     st.info(f"Timer Running: {elapsed}m")
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
                 st.caption("(Timer available on Tasks)")
        
        with col_t2:
            total = get_total_time(node_id, data["nodes"])
            st.metric("Total Time", format_time(total))

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
                 res = analyze_node(node_id, data["nodes"])
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
            
            if analysis.get("proposed_tasks"):
                st.markdown("#### 🚀 Proposed Missing Tasks")
                for task in analysis["proposed_tasks"]:
                    c1, c2 = st.columns([0.8, 0.2])
                    c1.markdown(f"- {task}")
                    if c2.button("Add", key=f"add_prop_{task[:10]}_{node_id}"):
                         # 1. Find or Create "AI Actions" Initiative
                         ai_init_id = None
                         children_ids = node.get("children", [])
                         for cid in children_ids:
                             child = data["nodes"].get(cid)
                             # Robust search: title starts with the prefix or is the legacy exact name
                             child_title = child.get("title", "")
                             if child and (child_title == "🤖 AI Actions" or child_title.startswith("🤖 AI Actions:")):
                                 ai_init_id = cid
                                 break
                         
                         if not ai_init_id:
                             # Generate meaningful title
                             from services.gemini import suggest_initiative_title
                             with st.spinner("Generating initiative name..."):
                                 topic = suggest_initiative_title(task)
                                 
                             init_title = f"🤖 AI Actions: {topic}"
                             # Create it
                             ai_init_id = add_node(data, node_id, "INITIATIVE", init_title, "Container for AI proposed tasks", username)
                         
                         # 2. Add Task under it
                         add_node(data, ai_init_id, "TASK", task, "AI Proposed Task", username)
                         st.toast(f"Added task to '{data['nodes'][ai_init_id]['title']}': {task}")
                         st.rerun()

        elif analysis and isinstance(analysis, str):
             # Legacy content fallback
             st.info(analysis)

    st.markdown("---")
    if st.button("🗑️ Delete Entity", type="primary"):
        delete_node(data, node_id, username)
        # If deleted, we must pop stack if we were inside it? 
        # But we are in modal. After rerun, if node gone, we should handle logic.
        # Ideally pop stack if necessary.
        st.rerun()


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
            if node_type in ["INITIATIVE", "TASK"]:
                t = get_total_time(node_id, data["nodes"])
                stats += f" | ⏱️ {format_time(t)}"
            
            st.markdown(f"**{label}**")
            st.caption(stats)
            
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
                    with st.spinner("🧠 Gemini is auditing..."):
                        res = analyze_node(node_id, data["nodes"])
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
             normalized_btn = child_type.replace('_',' ').title()
             if st.button(f"➕ New {normalized_btn}", key=f"add_btn_{current_node['id']}"):
                 add_node(data, current_node["id"], child_type, f"New {normalized_btn}", "", username, cycle_id=st.session_state.active_cycle_id)
                 st.rerun()
    else:
        st.markdown(f"## {level_name}")
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
    st.sidebar.markdown(f"👤 **{username}**")
    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        del st.session_state["nav_stack"]
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
            if st.session_state.active_report_mode == "Ritual":
                render_weekly_ritual_dialog(data, username)
            elif st.session_state.active_report_mode == "Dashboard":
                render_leadership_dashboard_dialog(username)
            else:
                render_report_dialog(data, username, mode=st.session_state.active_report_mode)

def main():
    init_database() # Ensure tables exist
    if "username" not in st.session_state:
        render_login()
    else:
        render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
