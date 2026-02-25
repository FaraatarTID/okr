import logging


_LOGGER = logging.getLogger(__name__)
_LAST_SEEN_INVALIDATION_TS = 0


def clear_cache_safe():
    """Best-effort cache clear with cluster-wide invalidation broadcast."""
    try:
        import streamlit as st
        from src.services.distributed_state_service import broadcast_cache_invalidation

        st.cache_data.clear()
        # Broadcast to other nodes in the cluster
        if not broadcast_cache_invalidation():
            _LOGGER.warning("Failed to broadcast distributed cache invalidation.")
    except (ImportError, AttributeError, RuntimeError) as exc:
        _LOGGER.debug("Skipping Streamlit cache clear in current runtime: %s", exc)


def check_distributed_cache_staleness():
    """
    Check if another node has requested a cache clear.
    Call this at the beginning of top-level app execution.
    """
    global _LAST_SEEN_INVALIDATION_TS
    try:
        import streamlit as st
        from src.services.distributed_state_service import (
            get_last_invalidation_timestamp,
        )

        global_ts = get_last_invalidation_timestamp()
        if global_ts and global_ts != _LAST_SEEN_INVALIDATION_TS:
            _LOGGER.info(
                "Distributed cache invalidation detected (global_ts=%s). Clearing local cache.",
                global_ts,
            )
            st.cache_data.clear()
            _LAST_SEEN_INVALIDATION_TS = global_ts
    except Exception as exc:
        _LOGGER.debug("Failed to check distributed cache staleness: %s", exc)
