import os
from typing import Optional

import streamlit as st


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_production() -> bool:
    """Return True if production mode is enabled via env or secrets."""
    env_val = os.getenv("PRODUCTION")
    if _truthy(env_val):
        return True
    try:
        app_secrets = st.secrets.get("app")
        if isinstance(app_secrets, dict):
            return _truthy(app_secrets.get("production"))
    except Exception:
        pass
    return False
