import streamlit as st
import sys
import os
import time
from datetime import datetime

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, save_data, add_node, delete_node, update_node, update_node_progress, export_data, import_data, start_timer, stop_timer, get_total_time

st.set_page_config(page_title="OKR Tracker", layout="wide")

# Full hierarchy types matching Vite app
TYPES = ["GOAL", "STRATEGY", "OBJECTIVE", "KEY_RESULT", "INITIATIVE", "TASK"]

# Child type mapping: parent type -> default child type
CHILD_TYPE_MAP = {
    "GOAL": "STRATEGY",
    "STRATEGY": "OBJECTIVE", 
    "OBJECTIVE": "KEY_RESULT",
    "KEY_RESULT": "INITIATIVE",
    "INITIATIVE": "TASK",
    "TASK": None  # Tasks have no children
}

# Icons for each type
TYPE_ICONS = {
    "GOAL": "🎯",
    "STRATEGY": "🚀",
    "OBJECTIVE": "📍",
    "KEY_RESULT": "📈",
    "INITIATIVE": "💡",
    "TASK": "✅"
}

def format_time(minutes):
    """Format minutes into Xh Ym"""
    if not minutes:
         return "0m"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

def render_login():
    st.markdown("## 🔐 Login to OKR Tracker")
    st.info("👋 Welcome! Please enter your **Account Name** to access your data.")
    st.markdown("_(Note: If this is your first time, a new account will be created automatically.)_")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username = st.text_input("Account Name (Unique ID)", placeholder="e.g. john_doe")
        if st.button("Enter", type="primary"):
            if username.strip():
                st.session_state["username"] = username.strip()
                st.rerun()
            else:
                st.error("Please enter a valid name.")

def render_app(username):
    # Sidebar User Info
    st.sidebar.markdown(f"👤 **Logged in as:** `{username}`")
    if st.sidebar.button("Logout"):
        del st.session_state["username"]
        st.rerun()
    st.sidebar.markdown("---")

    st.title("🚀 OKR Tracker with Gemini AI")
    
    # Load data for specific user
    data = load_data(username)
    
    # Sidebar Actions
    st.sidebar.header("Actions")
    if st.sidebar.button("➕ Add New Goal"):
        add_node(data, None, "GOAL", "New Goal", "", username)
        st.success("Goal Added!")
        st.rerun()

    # Stats
    total_nodes = len(data["nodes"])
    st.sidebar.markdown(f"**Total Items:** {total_nodes}")
    
    # --- Export/Import Section ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Data Management")
    
    # Export
    export_json = export_data(username)
    filename = f"okr-backup-{username}-{datetime.now().strftime('%Y-%m-%d')}.json"
    st.sidebar.download_button(
        label="📥 Export Data",
        data=export_json,
        file_name=filename,
        mime="application/json",
        help="Download your OKR data as a JSON backup file"
    )
    
    # Import
    uploaded_file = st.sidebar.file_uploader(
        "📤 Import Data",
        type=["json"],
        help="Upload a JSON backup file to restore data"
    )
    
    if uploaded_file is not None:
        if st.sidebar.button("⚠️ Confirm Import (Overwrites Current Data)", type="primary"):
            content = uploaded_file.read().decode("utf-8")
            success, message = import_data(content, username)
            if success:
                st.sidebar.success(message)
                st.rerun()
            else:
                st.sidebar.error(message)

    # Render Roots
    st.markdown("---")
    root_ids = data.get("rootIds", [])
    if not root_ids:
        st.info("No Goals found. Start by adding one in the sidebar!")
    else:
        for root_id in root_ids:
             render_node(root_id, data, username, level=0)

def render_node(node_id, data, username, level=0):
    node = data["nodes"].get(node_id)
    if not node:
        return

    title = node.get('title', 'Untitled')
    progress = node.get('progress', 0)
    node_type = node.get('type', 'GOAL')
    children_ids = node.get("children", [])
    has_children = len(children_ids) > 0
    
    # Get icon for type
    icon = TYPE_ICONS.get(node_type, "📋")
    
    # Clean Title Display: "Goal #1" instead of "[GOAL] Goal #1"
    # Actually just allow the user title to speak for itself.
    # But user asked for: "in the title of stages in Streamlit I see the General Titles whithin brackets... nicer to be like: Goal #1"
    # The previous code was: label = f"{icon} [{node_type}] {title}"
    # New code: label = f"{icon} {title}"
    # The user can name the title "Goal #1". Or if they meant auto-numbering, that's complex.
    # Assuming they meant removal of `[GOAL]`.
    label = f"{icon} {title}"
    
    # Note: Streamlit Expanders can be nested
    with st.expander(label, expanded=node.get("isExpanded", True)):
        # Edit Form
        with st.form(key=f"edit_{node_id}"):
            new_title = st.text_input("Title", value=title)
            new_desc = st.text_area("Description", value=node.get("description", ""))
            
            # Progress Logic:
            col1, col2 = st.columns(2)
            with col1:
                if has_children:
                     st.metric("Progress (Calculated)", value=f"{progress}%")
                     new_progress = progress # Keep same
                else:
                     new_progress = st.slider("Progress (Manual)", 0, 100, value=progress)
            
            with col2:
                # Type selection
                current_index = TYPES.index(node_type) if node_type in TYPES else 0
                new_type = st.selectbox("Type", TYPES, index=current_index)

            if st.form_submit_button("Update Details"):
                update_node(data, node_id, {
                    "title": new_title,
                    "description": new_desc,
                    "progress": new_progress,
                    "type": new_type
                }, username)
                st.rerun()

        # --- Time Tracking Section (Initiatives & Tasks) ---
        if node_type in ["INITIATIVE", "TASK"]:
            st.markdown("---")
            t_col1, t_col2 = st.columns([1, 2])
            
            with t_col1:
                # Timer Controls - ONLY for TASKS
                if node_type == "TASK":
                    is_running = node.get("timerStartedAt") is not None
                    if is_running:
                         # Calculate elapsed for display (approximate since page load)
                         start_ts = node.get("timerStartedAt")
                         elapsed_current_session = int((time.time() * 1000 - start_ts) / 60000)
                         st.warning(f"⏱️ Running: +{elapsed_current_session}m")
                         if st.button("⏹️ Stop Timer", key=f"stop_{node_id}"):
                             stop_timer(data, node_id, username)
                             st.rerun()
                    else:
                         if st.button("▶️ Start Timer", key=f"start_{node_id}"):
                             start_timer(data, node_id, username)
                             st.rerun()
                else:
                    st.caption("(Timer available on Tasks)")
            
            with t_col2:
                # Total Time Display
                total_time = get_total_time(node_id, data["nodes"])
                st.info(f"**Total Time Spent:** {format_time(total_time)}")


        # AI Analysis Section (for KEY_RESULT type)
        if node_type == "KEY_RESULT":
            from services.gemini import analyze_node
            st.markdown("---")
            col_ai, col_score = st.columns([1, 4])
            if col_ai.button("✨ Analyze", key=f"btn_analyze_{node_id}"):
                with st.spinner("Consulting Gemini..."):
                    result = analyze_node(node_id, data["nodes"])
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state[f"analysis_{node_id}"] = result
                        # Update node store too?
                        update_node(data, node_id, {
                            "geminiScore": result["score"],
                            "geminiAnalysis": result["analysis"]
                        }, username)
                        st.rerun()

            # Show existing or session analysis
            analysis = st.session_state.get(f"analysis_{node_id}") or {
                "score": node.get("geminiScore"),
                "analysis": node.get("geminiAnalysis")
            }
            
            if analysis.get("analysis"):
                st.info(f"**Gemini Score:** {analysis.get('score')}/100\n\n{analysis.get('analysis')}")

        # Child Management
        st.markdown("---")
        col_add, col_del = st.columns([2, 1])
        
        # Determine if this node can have children
        child_type = CHILD_TYPE_MAP.get(node_type)
        
        with col_add:
            if child_type:
                if st.button(f"➕ Add {child_type}", key=f"btn_add_{node_id}"):
                    add_node(data, node_id, child_type, f"New {child_type.replace('_', ' ').title()}", "", username)
                    st.rerun()
            else:
                st.caption("(Tasks have no sub-items)")
                
        with col_del:
            if st.button("🗑️ Delete", key=f"btn_del_{node_id}", type="primary"):
                delete_node(data, node_id, username)
                st.rerun()

        # Render Children
        if children_ids:
            st.markdown(f"**Sub-items ({len(children_ids)})**")
            for child_id in children_ids:
                render_node(child_id, data, username, level=level+1)

def main():
    if "username" not in st.session_state:
        render_login()
    else:
        render_app(st.session_state["username"])

if __name__ == "__main__":
    main()
