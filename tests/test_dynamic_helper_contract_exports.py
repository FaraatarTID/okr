from __future__ import annotations


def test_app_helper_contract_exports_are_present():
    import app as app_module

    required = [
        "ensure_startup_ready",
        "prewarm_startup_ready_async",
        "should_run_startup_recovery",
        "authenticate_user_detailed",
        "reset_user_password",
    ]
    missing = [name for name in required if not hasattr(app_module, name)]
    assert not missing, f"Missing app helper contract exports: {missing}"


def test_components_compat_contract_exports_are_present():
    import src.ui.components as components

    required = [
        "can_track_task_timer",
        "inject_atlas_styles",
        "_atlas_health_index",
        "_build_atlas_treemap",
        "_atlas_is_mobile_request",
    ]
    missing = [name for name in required if not hasattr(components, name)]
    assert not missing, f"Missing components compatibility exports: {missing}"
