import streamlit as st
import sys
import os
import time
from datetime import datetime

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, save_data, add_node, delete_node, update_node, update_node_progress, export_data, import_data, start_timer, stop_timer, get_total_time

# Import streamlit-agraph for mind map visualization
from streamlit_agraph import agraph, Node, Edge, Config

st.set_page_config(page_title="OKR Tracker", layout="wide")

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
    "GOAL": "🎯",
    "STRATEGY": "🚀",
    "OBJECTIVE": "📍",
    "KEY_RESULT": "📈",
    "INITIATIVE": "💡",
    "TASK": "✅"
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

@st.dialog("🗺️ OKR Mind Map", width="large")
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


@st.dialog("Inspect & Edit")
def render_inspector_dialog(node_id, data, username):
    render_inspector_content(node_id, data, username)

def render_inspector_content(node_id, data, username):
    node = data["nodes"].get(node_id)
    if not node:
        st.error("Node not found")
        return

    title = node.get('title', 'Untitled')
    progress = node.get('progress', 0)
    node_type = node.get('type', 'GOAL')
    has_children = len(node.get("children", [])) > 0
    
    # Header
    st.markdown(f"### {TYPE_ICONS.get(node_type, '')} {title}")
    
    with st.form(key=f"edit_{node_id}"):
        new_title = st.text_input("Title", value=title)
        new_desc = st.text_area("Description", value=node.get("description", ""))
        
        col1, col2 = st.columns(2)
        with col1:
            if has_children:
                 st.metric("Progress (Calculated)", value=f"{progress}%")
                 new_progress = progress 
            else:
                 new_progress = st.slider("Progress (Manual)", 0, 100, value=progress)
        
        with col2:
            current_index = TYPES.index(node_type) if node_type in TYPES else 0
            new_type = st.selectbox("Type", TYPES, index=current_index)

        if st.form_submit_button("💾 Save Changes"):
            update_node(data, node_id, {
                "title": new_title,
                "description": new_desc,
                "progress": new_progress,
                "type": new_type
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
                     st.warning(f"Running: {elapsed}m")
                     if st.button("⏹️ Stop Timer"):
                         stop_timer(data, node_id, username)
                         st.rerun()
                else:
                     if st.button("▶️ Start Timer"):
                         start_timer(data, node_id, username)
                         st.rerun()
             else:
                 st.caption("(Timer available on Tasks)")
        
        with col_t2:
            total = get_total_time(node_id, data["nodes"])
            st.metric("Total Time", format_time(total))

    # AI Analysis (Key Result)
    if node_type == "KEY_RESULT":
        from services.gemini import analyze_node
        st.markdown("---")
        if st.button("✨ Gemini Analysis"):
             with st.spinner("Analyzing..."):
                 res = analyze_node(node_id, data["nodes"])
                 if "error" in res: st.error(res["error"])
                 else:
                     update_node(data, node_id, {"geminiAnalysis": res["analysis"], "geminiScore": res["score"]}, username)
                     st.rerun()
        
        if node.get("geminiAnalysis"):
            st.info(node["geminiAnalysis"])

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
        c1, c2, c3 = st.columns([4, 1, 1])
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
                     if st.button("⏹️", key=f"stop_card_{node_id}", help="Stop Timer"):
                         stop_timer(data, node_id, username)
                         st.rerun()
                 else:
                     if st.button("▶️", key=f"start_card_{node_id}", help="Start Timer"):
                         start_timer(data, node_id, username)
                         st.rerun()
             
             if st.button("🔍", key=f"inspect_{node_id}", help="Inspect & Edit"):
                 render_inspector_dialog(node_id, data, username)
             
             # View Map button - only show if node has children
             if has_children:
                 if st.button("🗺️", key=f"map_{node_id}", help="View Mind Map"):
                     render_mindmap_dialog(node_id, data)
                 
        with c3:
            # Navigation Button ("Open")
            # Only if not leaf
            if not is_leaf:
                 if st.button("➡️", key=f"nav_{node_id}", help="Drill Down"):
                     navigate_to(node_id)
            elif node_type == "TASK":
                 # Maybe show something else? or Empty?
                 pass

def render_level(data, username):
    stack = st.session_state.nav_stack
    
    # Determine what to show
    if not stack:
        # Root Level
        items = data.get("rootIds", [])
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
                 add_node(data, current_node["id"], child_type, f"New {normalized_btn}", "", username)
                 st.rerun()
    else:
        st.markdown(f"## {level_name}")
        if st.button("➕ New Goal"):
             add_node(data, None, "GOAL", "New Goal", "", username)
             st.rerun()

    st.markdown("---")
    
    if not items:
        st.info("No items here yet.")
    
    # Grid View for Cards? Or List? Cards usually look better in grid.
    # Let's do 2 cards per row.
    cols = st.columns(2)
    for i, item_id in enumerate(items):
        with cols[i % 2]:
            render_card(item_id, data, username)


def render_app(username):
    # Sidebar
    st.sidebar.markdown(f"👤 **{username}**")
    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        del st.session_state["nav_stack"]
        st.rerun()

    data = load_data(username)
    
    # Sidebar Utilities (Export)
    with st.sidebar.expander("Backup"):
        export_json = export_data(username)
        st.download_button("Export JSON", export_json, "backup.json")
        uploaded = st.file_uploader("Import", type=["json"])
        if uploaded and st.button("Import"):
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

    render_level(data, username)

def main():
    if "username" not in st.session_state:
        render_login()
    else:
        render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
