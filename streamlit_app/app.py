"""Thin Streamlit entry coordinator.

This module intentionally stays small and declarative:
1. Adapt environment/config/runtime data to helper modules.
2. Expose cached runtime snapshot utilities consumed by helper modules.
3. Delegate UI/auth/app-shell flows to focused helper modules.

Business logic should live in `src/ui/app_*_helpers.py` (or lower layers), not here.
"""

import streamlit as st
import sys
import os
import subprocess
from datetime import datetime

# Keep `import app` stable for test/runtime contexts that execute from repo root.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Database utilities
from src.audit import error_log
from src.bootstrap import (
    ensure_startup_ready,  # noqa: F401 - exported for auth helper module contract
    prewarm_startup_ready_async,  # noqa: F401 - exported for auth helper module contract
    should_run_startup_recovery,  # noqa: F401 - exported for auth helper module contract
)
from src.config_runtime import (
    get_bool_config,
    get_config_value,
    get_config_value_with_source,
)
from src.crud import (
    get_all_cycles,
    create_cycle,
    # User Auth dependencies are resolved dynamically by helper modules via app_module.
    authenticate_user_detailed,  # noqa: F401 - exported for auth helper module contract
    reset_user_password,  # noqa: F401 - exported for auth helper module contract
    get_user_by_id,
)
from src.models import UserRole
from src.runtime_preflight import evaluate_runtime_preflight
from src.ui import (
    app_auth_helpers,
    app_entry_helpers,
    app_network_helpers,
    app_preflight_helpers,
    app_runtime_helpers,
    app_shell_helpers,
)
from src.utils.time_utils import utc_now_naive


# ---------------------------------------------------------------------------
# Runtime Preflight Adapters
# ---------------------------------------------------------------------------
# These adapter functions pass app-local dependencies into the dedicated
# preflight helper module. This keeps orchestration here, policy there.
def _get_pdf_method() -> str:
    """Resolve effective PDF backend method."""
    return app_preflight_helpers.get_pdf_method(
        cfg_value_fn=_cfg_value,
        has_pdfshift_api_key_fn=_has_pdfshift_api_key,
    )


def _is_streamlit_cloud_runtime() -> bool:
    """Detect Streamlit Cloud deployment environment."""
    return app_preflight_helpers.is_streamlit_cloud_runtime(environ=os.environ)


def _has_pdfshift_api_key() -> bool:
    """Check if PDFShift credentials are configured."""
    return app_preflight_helpers.has_pdfshift_api_key(
        cfg_value_fn=_cfg_value,
    )


def _runtime_preflight_strict_mode() -> bool:
    """Resolve strict-mode flag for runtime preflight policy."""
    return app_preflight_helpers.runtime_preflight_strict_mode(
        cfg_value_fn=_cfg_value
    )


def _cfg_value(name: str, default: str = "") -> str:
    """Read string config value with legacy compatibility handled downstream."""
    return get_config_value(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    """Read boolean config value."""
    return get_bool_config(name, default)


def _env_bool_with_legacy(name: str, legacy_name: str, default: bool = False) -> bool:
    """Support renamed feature flags while preserving old env var behavior."""
    return app_preflight_helpers.env_bool_with_legacy(
        name=name,
        legacy_name=legacy_name,
        default=default,
        cfg_value_fn=_cfg_value,
        env_bool_fn=_env_bool,
    )


def _run_pdf_preflight():
    """Run one-time startup/runtime safeguards before authenticated workspace load."""
    # Keep imports lazy so login cold-start remains fast.
    from src.services.ai_service import get_api_key
    from src.services.ai_provider import (
        get_ai_provider_runtime_status,
        is_external_ai_allowed,
    )
    return app_preflight_helpers.run_pdf_preflight(
        st_module=st,
        environ=os.environ,
        cfg_value_fn=_cfg_value,
        env_bool_fn=_env_bool,
        get_config_value_with_source_fn=get_config_value_with_source,
        evaluate_runtime_preflight_fn=evaluate_runtime_preflight,
        get_api_key_fn=get_api_key,
        get_ai_provider_runtime_status_fn=get_ai_provider_runtime_status,
        is_external_ai_allowed_fn=is_external_ai_allowed,
        get_pdf_method_fn=_get_pdf_method,
        has_pdfshift_api_key_fn=_has_pdfshift_api_key,
        is_streamlit_cloud_runtime_fn=_is_streamlit_cloud_runtime,
        runtime_preflight_strict_mode_fn=_runtime_preflight_strict_mode,
    )


# ---------------------------------------------------------------------------
# Runtime Snapshot / Cache Adapters
# ---------------------------------------------------------------------------
# These wrappers define cache boundaries and adapter wiring for runtime helpers.
def _cycle_to_snapshot(cycle) -> dict | None:
    """Convert ORM cycle object into cache-safe primitive snapshot."""
    return app_runtime_helpers.cycle_to_snapshot(cycle)


def _date_label(value) -> str:
    """Format a date-like value for cycle labels."""
    return app_runtime_helpers.date_label(value)


def _format_cycle_label(cycle_snapshot: dict) -> str:
    """Build user-facing cycle selector label from snapshot data."""
    return app_runtime_helpers.format_cycle_label(
        cycle_snapshot,
        date_label_fn=_date_label,
    )


def _build_cycle_selector_payload(cycles: list[dict]) -> tuple[list[int], dict[int, str]]:
    """Return ID-backed selector options plus display labels."""
    return app_runtime_helpers.build_cycle_selector_payload(
        cycles,
        format_cycle_label_fn=_format_cycle_label,
    )


@st.cache_data(ttl=30, show_spinner=False)
def _cached_get_all_cycles():
    """Cache cycle list snapshots to reduce rerun query pressure."""
    return app_runtime_helpers.cached_get_all_cycles(
        get_all_cycles_fn=get_all_cycles,
        cycle_to_snapshot_fn=_cycle_to_snapshot,
    )


def _bootstrap_default_cycle_if_needed(
    cycles: list[dict], *, username: str, user_role: str
) -> tuple[list[dict], str | None]:
    """Create a default cycle only when policy allows and none exist."""
    return app_runtime_helpers.bootstrap_default_cycle_if_needed(
        cycles,
        username=username,
        user_role=user_role,
        admin_role_value=UserRole.ADMIN.value,
        utc_now_naive_fn=utc_now_naive,
        create_cycle_fn=create_cycle,
        cycle_to_snapshot_fn=_cycle_to_snapshot,
        clear_cycles_cache_fn=_cached_get_all_cycles.clear,
        error_log_fn=error_log,
    )


@st.cache_data(ttl=10, show_spinner=False)
def _cached_get_user_runtime_snapshot(user_id: int):
    """Cache current user's runtime identity snapshot."""
    return app_runtime_helpers.cached_get_user_runtime_snapshot(
        int(user_id),
        get_user_by_id_fn=get_user_by_id,
        build_runtime_user_snapshot_fn=_build_runtime_user_snapshot,
    )


def _weekly_plan_cache_bucket(now: datetime | None = None) -> str:
    """Bucket weekly plan cache by week start to avoid per-rerun churn."""
    return app_runtime_helpers.weekly_plan_cache_bucket(
        now=now,
        utc_now_naive_fn=utc_now_naive,
    )


@st.cache_data(ttl=10, show_spinner=False)
def _cached_get_active_weekly_plan_snapshot(user_id: int, week_bucket: str):
    """Cache active weekly plan snapshot for current week bucket."""
    from src.crud import get_active_weekly_plan

    return app_runtime_helpers.cached_get_active_weekly_plan_snapshot(
        int(user_id),
        week_bucket,
        get_active_weekly_plan_fn=get_active_weekly_plan,
    )


def _get_active_weekly_plan_snapshot(user_id: int, now: datetime | None = None):
    """Resolve active weekly plan via bucketed cache strategy."""
    return app_runtime_helpers.get_active_weekly_plan_snapshot(
        int(user_id),
        now=now,
        weekly_plan_cache_bucket_fn=_weekly_plan_cache_bucket,
        cached_get_active_weekly_plan_snapshot_fn=_cached_get_active_weekly_plan_snapshot,
    )


def _should_warn_default_admin_password(user_snapshot: dict | None) -> bool:
    # Startup bootstrap enforces `must_change_password` for default credentials,
    # so runtime warning can safely key off this computed snapshot signal.
    return app_runtime_helpers.should_warn_default_admin_password(
        user_snapshot,
        admin_role_value=UserRole.ADMIN.value,
    )


def _build_runtime_user_snapshot(user) -> dict | None:
    """Project runtime-safe user fields from ORM entity."""
    return app_runtime_helpers.build_runtime_user_snapshot(user)


def _resolve_app_shell_runtime_from_user_snapshot(snapshot: dict | None) -> dict:
    """Build full app-shell runtime bundle from user snapshot + cached deps."""
    return app_runtime_helpers.resolve_app_shell_runtime_from_user_snapshot(
        snapshot,
        cached_get_all_cycles_fn=_cached_get_all_cycles,
        get_active_weekly_plan_snapshot_fn=_get_active_weekly_plan_snapshot,
        should_warn_default_admin_password_fn=_should_warn_default_admin_password,
    )


def _resolve_app_shell_runtime(user_id: int) -> dict:
    """Resolve app-shell runtime bundle for current user id."""
    return app_runtime_helpers.resolve_app_shell_runtime(
        int(user_id),
        cached_get_user_runtime_snapshot_fn=_cached_get_user_runtime_snapshot,
        resolve_app_shell_runtime_from_user_snapshot_fn=_resolve_app_shell_runtime_from_user_snapshot,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _get_build_fingerprint() -> str:
    """Best-effort runtime build marker to diagnose stale cloud deployments."""
    env_sha = str(
        os.getenv("STREAMLIT_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or os.getenv("SOURCE_COMMIT")
        or ""
    ).strip()
    if env_sha:
        return env_sha[:8]

    try:
        repo_root = os.path.dirname(os.path.abspath(__file__))
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if sha:
            return sha
    except Exception:
        pass

    return "unknown"


# Modular UI Components (lazy import in render_app to speed initial load)
st.set_page_config(page_title="OKR Tracker", layout="wide")


# Basic error reporting hook
def _excepthook(exc_type, exc, tb):
    try:
        error_log("Uncaught exception", exc)
    finally:
        # Preserve default behavior
        sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _excepthook


# ---------------------------------------------------------------------------
# Thin Delegation Wrappers
# ---------------------------------------------------------------------------
# Keep entry-level functions stable for imports/tests, but delegate all heavy
# logic to focused helper modules.
def _get_client_ip() -> str | None:
    """Extract best-effort client IP from Streamlit request context."""
    return app_network_helpers.get_client_ip_from_streamlit(st_module=st)


def render_login():
    """Render login form and authentication flow."""
    return app_auth_helpers.render_login_from_app(app_module=sys.modules[__name__])


def _clear_user_session():
    """Clear auth/navigation/session keys on logout or invalid session."""
    return app_auth_helpers.clear_user_session(st.session_state)


def render_password_reset_gate():
    """Render forced password-reset flow for temporary/initial credentials."""
    return app_auth_helpers.render_password_reset_gate_from_app(
        app_module=sys.modules[__name__]
    )


def render_app(username, runtime_bundle=None):
    """Render authenticated workspace shell."""
    return app_shell_helpers.render_app_from_app(
        app_module=sys.modules[__name__],
        username=username,
        runtime_bundle=runtime_bundle,
    )


def main():
    """Top-level app entrypoint."""
    return app_entry_helpers.run_main_from_app(app_module=sys.modules[__name__])


if __name__ == "__main__":
    main()
