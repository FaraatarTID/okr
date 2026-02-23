"""Admin and management dialog coordinators."""

from __future__ import annotations

from src.ui import dialogs_admin_cycles_helpers
from src.ui import dialogs_admin_leadership_helpers
from src.ui import dialogs_admin_panel_helpers


def render_manage_cycles_dialog_content() -> None:
    dialogs_admin_cycles_helpers.render_manage_cycles_dialog_content()


def render_leadership_dashboard_dialog_content(
    *,
    username: str,
    render_leadership_dashboard_content_fn,
    render_strategy_pulse_content_fn,
) -> None:
    dialogs_admin_leadership_helpers.render_leadership_dashboard_dialog_content(
        username=username,
        render_leadership_dashboard_content_fn=render_leadership_dashboard_content_fn,
        render_strategy_pulse_content_fn=render_strategy_pulse_content_fn,
    )


def render_admin_panel_dialog_content() -> None:
    dialogs_admin_panel_helpers.render_admin_panel_dialog_content()
