"""Admin-panel backup/restore tab helpers."""

from __future__ import annotations

import streamlit as st

from src.config_runtime import get_bool_config
from src.utils.time_utils import utc_now_naive


def render_backup_tab_content() -> None:
    """Render the admin backup/restore tab."""
    from src.database import (
        BACKUP_FORMAT_VERSION,
        export_database_backup,
        import_database_backup,
    )
    from src.domain.password_policy import is_production_runtime
    from src.services.backend_client import is_backend_enabled

    st.markdown("#### Full Database Backup")
    st.caption(
        "Export a full logical JSON backup or restore one. "
        "Restore replaces all current application data."
    )

    proxy_mutations = get_bool_config("OKR_BACKEND_PROXY_MUTATIONS", True)
    explicit_restore_override = get_bool_config("OKR_ENABLE_DIRECT_DB_RESTORE", False)
    restore_allowed = (
        explicit_restore_override
        and not is_production_runtime()
        and not (proxy_mutations and is_backend_enabled())
    )
    if not explicit_restore_override:
        st.warning(
            "Direct DB restore from Streamlit is disabled by default. "
            "Use backend/operator maintenance procedures for restore operations."
        )
    elif is_production_runtime():
        st.warning(
            "Direct DB restore is blocked in production runtime. "
            "Use backend/operator maintenance procedures for restore operations."
        )
    elif proxy_mutations and is_backend_enabled():
        st.warning(
            "Direct DB restore is disabled while backend-assisted mutation mode is active. "
            "Use backend maintenance procedures for restore operations."
        )

    export_col, import_col = st.columns(2)

    with export_col:
        st.markdown("##### Export")
        if st.button("Prepare Backup File", key="admin_prepare_backup"):
            try:
                backup_bytes = export_database_backup()
                st.session_state["admin_backup_bytes"] = backup_bytes
                st.session_state["admin_backup_created_at"] = utc_now_naive().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )
                st.success("Backup file prepared.")
            except Exception as exc:
                st.error(f"Backup export failed: {exc}")

        prepared_bytes = st.session_state.get("admin_backup_bytes")
        if prepared_bytes:
            created_at = st.session_state.get("admin_backup_created_at", "unknown")
            st.download_button(
                label="Download Backup",
                data=prepared_bytes,
                file_name=f"okr_backup_{created_at}.json",
                mime="application/json",
                key="admin_download_backup",
            )
            st.caption(f"Format: `{BACKUP_FORMAT_VERSION}`")

    with import_col:
        st.markdown("##### Import")
        uploaded_backup = st.file_uploader(
            "Upload backup file",
            type=["json"],
            key="admin_backup_upload",
            accept_multiple_files=False,
        )
        confirm_restore = st.checkbox(
            "I understand this will overwrite all current OKR data.",
            key="admin_backup_confirm_restore",
        )
        confirm_phrase = st.text_input(
            "Type RESTORE to confirm",
            key="admin_backup_confirm_phrase",
            placeholder="RESTORE",
        )

        restore_disabled = (
            uploaded_backup is None
            or not confirm_restore
            or confirm_phrase.strip() != "RESTORE"
            or not restore_allowed
        )
        if st.button(
            "Restore Backup",
            type="primary",
            key="admin_restore_backup",
            disabled=restore_disabled,
        ):
            try:
                result = import_database_backup(uploaded_backup.getvalue())
                st.success("Backup restored successfully.")
                restored_counts = result.get("restored_counts", {})
                if restored_counts:
                    with st.expander("Restored rows by table", expanded=True):
                        for table_name, row_count in restored_counts.items():
                            st.write(f"- `{table_name}`: {row_count}")
                unknown_tables = result.get("unknown_tables") or []
                if unknown_tables:
                    st.warning(
                        "Backup included unknown tables that were ignored: "
                        + ", ".join(unknown_tables)
                    )
                st.rerun()
            except Exception as exc:
                st.error(f"Backup import failed: {exc}")
