"""App shell orchestration helpers extracted from app.py."""

from __future__ import annotations


def render_app_from_app(*, app_module, username: str, runtime_bundle=None) -> None:
    """Render the authenticated app shell using dependencies from app_module."""
    st = app_module.st
    app_module._run_pdf_preflight()

    # Lazy imports to keep login path fast.
    from src.ui.styles import apply_custom_fonts, inject_dialog_styles
    from src.ui.components import render_level
    from src.ui.dialogs import (
        render_weekly_report_dialog,
        render_daily_report_dialog,
        render_inspector_dialog,
        render_retrobox_dialog,
        render_timeline_dialog,
        render_create_goal_dialog,
        render_create_objective_dialog,
        render_create_kr_dialog,
        render_weekly_ritual_dialog,
        render_timer_dialog,
        render_leadership_dashboard_dialog,
        render_admin_panel_dialog,
        render_create_task_dialog,
        render_manage_cycles_dialog,
    )

    apply_custom_fonts()
    inject_dialog_styles()

    if "nav_stack" not in st.session_state:
        st.session_state.nav_stack = []

    runtime_bundle = runtime_bundle or app_module._resolve_app_shell_runtime(
        int(st.session_state.get("user_id"))
    )
    current_user_snapshot = runtime_bundle.get("user")
    cycles = runtime_bundle.get("cycles", [])
    weekly_plan = runtime_bundle.get("weekly_plan")

    display_name = st.session_state.get("display_name", username)
    user_role = st.session_state.get("user_role", "member")

    st.sidebar.markdown(f"User: **{display_name}** ({user_role.title()})")
    if st.sidebar.button("Logout"):
        app_module._clear_user_session()
        st.rerun()

    if st.session_state.get("user_role") == "admin":
        if runtime_bundle.get("show_admin_default_password_warning"):
            st.sidebar.warning(
                "Default admin password is still active. Change it in Admin Panel."
            )
        if st.sidebar.button("Admin Panel", use_container_width=True):
            st.session_state.active_report_mode = "Admin"
            st.rerun()

    st.sidebar.markdown("---")

    cycles, cycles_error = app_module._bootstrap_default_cycle_if_needed(
        cycles,
        username=username,
        user_role=user_role,
    )
    if cycles_error:
        st.error(cycles_error)
        return

    st.sidebar.markdown("### OKR Cycle")
    cycle_ids, cycle_labels = app_module._build_cycle_selector_payload(cycles)
    if not cycle_ids:
        st.error("No cycles available. Create one from Admin Panel -> Manage Cycles.")
        return

    if "active_cycle_id" not in st.session_state:
        st.session_state.active_cycle_id = cycle_ids[0]
    active_cycle_id = int(st.session_state.get("active_cycle_id", cycle_ids[0]))
    if active_cycle_id not in cycle_ids:
        active_cycle_id = cycle_ids[0]
        st.session_state.active_cycle_id = active_cycle_id

    current_cycle_index = cycle_ids.index(active_cycle_id)
    selected_cycle_id = int(
        st.sidebar.selectbox(
            "Select Cycle",
            options=cycle_ids,
            format_func=lambda cid: cycle_labels.get(cid, f"Cycle #{cid}"),
            index=current_cycle_index,
            label_visibility="collapsed",
        )
    )

    if st.sidebar.button("Manage Cycles", key="manage_cycles_sidebar"):
        render_manage_cycles_dialog()

    if selected_cycle_id != active_cycle_id:
        st.session_state.active_cycle_id = selected_cycle_id
        st.session_state.nav_stack = []
        for key in [
            "atlas_selected_ref",
            "atlas_jump_query",
            "atlas_breadcrumbs",
            "atlas_focus_task_ref",
            "atlas_focus_task_picker",
            "atlas_last_selected_ref",
            "atlas_map_lens",
            "atlas_map_last_click_ref",
            "atlas_commit_preset",
            "atlas_commit_custom_min",
            "atlas_sprint_target_minutes",
            "atlas_sprint_task_ref",
            "atlas_sprint_started_at_epoch",
            "atlas_sprint_reminder_dismissed_for",
            "atlas_sprint_notification_sent_for",
            "atlas_last_session_summary",
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    st.sidebar.markdown("---")
    st.session_state["workspace_mode"] = "Atlas"
    if user_role == "admin":
        st.sidebar.markdown("### Experience")
        st.sidebar.success("Atlas Workspace Active")
        st.sidebar.caption(f"Build `{app_module._get_build_fingerprint()}`")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Navigation")
    if st.sidebar.button("Home / OKRs", use_container_width=True):
        if "active_report_mode" in st.session_state:
            del st.session_state.active_report_mode
        st.session_state.nav_stack = []
        for key in [
            "atlas_selected_ref",
            "atlas_breadcrumbs",
            "atlas_focus_task_ref",
            "atlas_focus_task_picker",
            "atlas_last_selected_ref",
            "atlas_map_lens",
            "atlas_map_last_click_ref",
            "atlas_commit_preset",
            "atlas_commit_custom_min",
            "atlas_sprint_target_minutes",
            "atlas_sprint_task_ref",
            "atlas_sprint_started_at_epoch",
            "atlas_sprint_reminder_dismissed_for",
            "atlas_sprint_notification_sent_for",
            "atlas_last_session_summary",
            "active_inspector_id",
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    st.sidebar.markdown("### Insights & Reports")
    dialog_active = False

    if st.sidebar.button("Weekly Report", use_container_width=True):
        st.session_state.active_report_mode = "Weekly"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button("Daily Report", use_container_width=True):
        st.session_state.active_report_mode = "Daily"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "Weekly Ritual",
        help="Guided check-in for your metrics",
        use_container_width=True,
    ):
        st.session_state.active_report_mode = "Ritual"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "RetroBox", help="Weekly retrospectives", use_container_width=True
    ):
        st.session_state.active_report_mode = "RetroBox"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "Project Timeline", help="Smart Gantt Chart", use_container_width=True
    ):
        st.session_state.active_report_mode = "Timeline"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if st.sidebar.button(
        "Strategic Dashboard",
        help="Executive visibility",
        use_container_width=True,
    ):
        st.session_state.active_report_mode = "Dashboard"
        if "active_timer_node_id" in st.session_state:
            del st.session_state.active_timer_node_id
        if "active_inspector_id" in st.session_state:
            del st.session_state.active_inspector_id
        st.rerun()

    if current_user_snapshot and weekly_plan:
        with st.container(border=True):
            c_wc1, c_wc2 = st.columns([0.15, 0.85])
            with c_wc1:
                st.markdown("### Focus")
                st.caption("Weekly Focus")
            with c_wc2:
                priorities = [
                    p
                    for p in [
                        weekly_plan.get("priority_1"),
                        weekly_plan.get("priority_2"),
                        weekly_plan.get("priority_3"),
                    ]
                    if p
                ]

                if not priorities:
                    st.info("No priorities set for this week.")
                else:
                    cols = st.columns(len(priorities))
                    for idx, priority in enumerate(priorities):
                        with cols[idx]:
                            st.markdown(f"**{idx + 1}.** {priority}")

    render_level(username)

    if not dialog_active:
        if "active_timer_node_id" in st.session_state:
            render_timer_dialog(st.session_state.active_timer_node_id, username)
        elif "active_inspector_id" in st.session_state:
            render_inspector_dialog(st.session_state.active_inspector_id, username)
        elif "active_report_mode" in st.session_state:
            mode = st.session_state.active_report_mode
            if mode == "Ritual":
                render_weekly_ritual_dialog(username)
            elif mode == "Dashboard":
                render_leadership_dashboard_dialog(username)
            elif mode == "Admin":
                render_admin_panel_dialog()
            elif mode == "Weekly":
                render_weekly_report_dialog(username)
            elif mode == "Daily":
                render_daily_report_dialog(username)
            elif mode == "RetroBox":
                render_retrobox_dialog(username)
            elif mode == "Timeline":
                render_timeline_dialog(username)

        if "add_mode_type" in st.session_state:
            ntype = st.session_state.add_mode_type
            parent_id = st.session_state.get("add_mode_parent")

            if ntype == "GOAL":
                render_create_goal_dialog(username)
            elif ntype == "OBJECTIVE":
                render_create_objective_dialog(parent_id)
            elif ntype == "KEY_RESULT":
                render_create_kr_dialog(parent_id)
            elif ntype == "TASK":
                render_create_task_dialog(parent_id, username)
