import streamlit as st

def navigate_to(node_id):
    """Push node to stack."""
    if "nav_stack" not in st.session_state: st.session_state.nav_stack = []
    st.session_state.nav_stack.append(node_id)
    st.rerun()

def navigate_back_to(index):
    """Pop stack to specific index."""
    if "nav_stack" not in st.session_state: st.session_state.nav_stack = []
    if index < 0:
        st.session_state.nav_stack = []
    else:
        st.session_state.nav_stack = st.session_state.nav_stack[:index+1]
    st.rerun()

def render_breadcrumbs(data):
    """Render clickable breadcrumbs using pills."""
    stack = st.session_state.get("nav_stack", [])
    options = ["HOME"] + stack
    
    def get_label(opt):
        if opt == "HOME":
           return "🏠 Home"
        node = data["nodes"].get(opt)
        if not node: return "Unknown"
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
        key="nav_pills",
        label_visibility="collapsed"
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
