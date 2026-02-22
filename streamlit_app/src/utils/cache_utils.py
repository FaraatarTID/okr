import logging


_LOGGER = logging.getLogger(__name__)


def clear_cache_safe():
    """Best-effort cache clear without hard dependency on Streamlit."""
    try:
        import streamlit as st
        st.cache_data.clear()
    except (ImportError, AttributeError, RuntimeError) as exc:
        _LOGGER.debug("Skipping Streamlit cache clear in current runtime: %s", exc)
