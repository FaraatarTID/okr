import importlib

import pytest


REMAINING_HELPER_MODULES = [
    "app_preflight_helpers",
    "app_runtime_helpers",
    "app_shell_navigation_helpers",
    "atlas_cached_read_helpers",
    "atlas_focus_section_helpers",
    "atlas_graph_helpers",
    "atlas_helpers",
    "atlas_index_helpers",
    "atlas_runtime_cache_helpers",
    "atlas_scope_snapshot_helpers",
    "atlas_selection_health_helpers",
    "atlas_treemap_helpers",
    "atlas_workspace_ai_helpers",
    "components_bridge_helpers",
    "dialogs_cache_helpers",
    "dialogs_create_chrome_helpers",
    "dialogs_create_helpers",
    "dialogs_inspector_helpers",
    "dialogs_mindmap_helpers",
    "dialogs_retro_helpers",
    "dialogs_ritual_checkin_helpers",
    "dialogs_ritual_helpers",
    "dialogs_ritual_plan_helpers",
    "dialogs_ritual_review_helpers",
    "dialogs_timeline_helpers",
    "model_binding_helpers",
]


@pytest.mark.parametrize("module_name", REMAINING_HELPER_MODULES)
def test_remaining_helper_module_imports_and_exposes_callables(module_name):
    module = importlib.import_module(f"src.ui.{module_name}")
    public_callables = [
        name
        for name, value in vars(module).items()
        if callable(value) and not name.startswith("_")
    ]
    private_callables = [
        name
        for name, value in vars(module).items()
        if callable(value) and name.startswith("_")
    ]

    assert module is not None
    assert public_callables or private_callables
