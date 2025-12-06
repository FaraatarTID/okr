import streamlit as st
import sys
import os

# Add current directory to path so we can import modules if running from outside
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.storage import load_data, save_data, add_node, delete_node, update_node, update_node_progress
from services.gemini import analyze_node

st.set_page_config(page_title="OKR Tracker", layout="wide")

# Valid types
TYPES = ["OBJECTIVE", "KEY_RESULT", "INITIATIVE"]

def main():
    st.title("🚀 OKR Tracker with Gemini AI")
    
    # Load data
    data = load_data()
    
    # Sidebar
    st.sidebar.header("Actions")
    if st.sidebar.button("Add New Objective"):
        add_node(data, None, "OBJECTIVE", "New Objective", "")
        st.success("Objective Added!")
        st.rerun()

    # Stats
    total_nodes = len(data["nodes"])
    st.sidebar.markdown(f"**Total Items:** {total_nodes}")

    # Render Roots
    root_ids = data.get("rootIds", [])
    if not root_ids:
        st.info("No Objectives found. Start by adding one in the sidebar!")
    else:
        for root_id in root_ids:
             render_node(root_id, data, level=0)

def render_node(node_id, data, level=0):
    node = data["nodes"].get(node_id)
    if not node:
        return

    title = node.get('title', 'Untitled')
    progress = node.get('progress', 0)
    node_type = node.get('type', 'Item')
    
    # Color coding/Emoji based on Type
    icon = "🎯" if node_type == "OBJECTIVE" else "📈" if node_type == "KEY_RESULT" else "📝"
    
    label = f"{icon} [{node_type}] {title} - {progress}%"
    
    # Note: Streamlit Expanders can be nested
    with st.expander(label, expanded=node.get("isExpanded", True)):
        # Edit Form
        with st.form(key=f"edit_{node_id}"):
            new_title = st.text_input("Title", value=title)
            new_desc = st.text_area("Description", value=node.get("description", ""))
            
            col1, col2 = st.columns(2)
            with col1:
                new_progress = st.slider("Progress", 0, 100, value=progress)
            
            with col2:
                # Type selection
                new_type = st.selectbox("Type", TYPES, index=TYPES.index(node_type) if node_type in TYPES else 0)

            if st.form_submit_button("Update Details"):
                update_node(data, node_id, {
                    "title": new_title,
                    "description": new_desc,
                    "progress": new_progress,
                    "type": new_type
                })
                st.rerun()

        # AI Analysis Section
        if node_type == "KEY_RESULT":
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
                        })
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
        
        with col_add:
            if st.button("➕ Add Child", key=f"btn_add_{node_id}"):
                child_type = "KEY_RESULT" if node_type == "OBJECTIVE" else "INITIATIVE"
                add_node(data, node_id, child_type, "New Child", "")
                st.rerun()
                
        with col_del:
            if st.button("🗑️ Delete", key=f"btn_del_{node_id}", type="primary"):
                delete_node(data, node_id)
                st.rerun()

        # Render Children
        children_ids = node.get("children", [])
        if children_ids:
            st.markdown(f"**Sub-items ({len(children_ids)})**")
            for child_id in children_ids:
                render_node(child_id, data, level=level+1)

if __name__ == "__main__":
    main()
