import streamlit as st
import sys
import os
import time
from datetime import datetime

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, save_data, add_node, delete_node, update_node, update_node_progress, export_data, import_data, start_timer, stop_timer, get_total_time

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

def format_time(minutes):
    if not minutes: return "0m"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

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
    """Render clickable breadcrumbs."""
    stack = st.session_state.nav_stack
    
    cols = st.columns(len(stack) + 2)
    
    # Root Home
    with cols[0]:
        if st.button("🏠 Home", key="crumb_home"):
            navigate_back_to(-1)
            
    # Breadcrumbs
    for i, node_id in enumerate(stack):
        node = data["nodes"].get(node_id)
        title = node.get("title", "Untitled") if node else "Unknown"
        # Truncate long titles
        short_title = (title[:15] + '..') if len(title) > 15 else title
        
        with cols[i+1]:
            st.write(" > ")
            if st.button(short_title, key=f"crumb_{i}"):
                navigate_back_to(i)

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
        st.markdown(f"## {level_name} ({len(items)})")
        st.caption(f"Inside: {current_node.get('title')}")
        
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
        st.markdown(f"## {level_name} ({len(items)})")
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

    render_level(data, username)

def main():
    if "username" not in st.session_state:
        render_login()
    else:
        render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
