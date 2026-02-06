def clear_cache_safe():
    """Best-effort cache clear without hard dependency on Streamlit."""
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass
