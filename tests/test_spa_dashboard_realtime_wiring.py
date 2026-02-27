from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATLAS_SHELL_PATH = ROOT / "spa-web" / "src" / "components" / "AtlasShell.tsx"
ATLAS_API_PATH = ROOT / "spa-web" / "src" / "lib" / "api" / "atlas.ts"
ADMIN_API_PATH = ROOT / "spa-web" / "src" / "lib" / "api" / "admin.ts"
JOBS_API_PATH = ROOT / "spa-web" / "src" / "lib" / "api" / "jobs.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_block(source: str, function_name: str) -> str:
    marker = f"export async function {function_name}("
    start = source.find(marker)
    assert start >= 0, f"Function not found: {function_name}"
    end = source.find("\nexport async function ", start + len(marker))
    if end < 0:
        end = len(source)
    return source[start:end]


def test_dashboard_has_live_refresh_polling_and_focus_sync() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;" in source
    assert 'mode !== "dashboard" && mode !== "timeline"' in source
    assert "window.setInterval(refreshFromSignal, DASHBOARD_REFRESH_INTERVAL_MS)" in source
    assert 'window.addEventListener("focus", refreshFromSignal)' in source
    assert 'document.addEventListener("visibilitychange", refreshFromSignal)' in source
    assert source.count("await refreshDashboardModeData(user, mode);") >= 2


def test_atlas_shell_delegates_admin_mode_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/AdminModePanel\"" in source
    assert ") : mode === \"admin\" ? (" in source
    assert "<AdminModePanel" in source


def test_atlas_shell_delegates_dashboard_leadership_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/DashboardLeadershipPanel\"" in source
    assert "<DashboardLeadershipPanel" in source


def test_atlas_shell_delegates_timeline_mode_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/TimelineModePanel\"" in source
    assert "<TimelineModePanel" in source


def test_atlas_shell_delegates_weekly_mode_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/WeeklyModePanel\"" in source
    assert "<WeeklyModePanel" in source


def test_atlas_shell_delegates_daily_mode_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/DailyModePanel\"" in source
    assert "<DailyModePanel" in source


def test_atlas_shell_delegates_ritual_mode_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/RitualModePanel\"" in source
    assert "<RitualModePanel" in source


def test_atlas_shell_delegates_retrobox_mode_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/RetroboxModePanel\"" in source
    assert "<RetroboxModePanel" in source


def test_atlas_shell_delegates_focus_map_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/AtlasFocusMapPanel\"" in source
    assert "<AtlasFocusMapPanel" in source


def test_atlas_shell_delegates_atlas_mode_controls_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/AtlasModeControlsPanel\"" in source
    assert "<AtlasModeControlsPanel" in source


def test_atlas_shell_delegates_inspector_ai_assist_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/InspectorAiAssistPanel\"" in source
    assert "<InspectorAiAssistPanel" in source


def test_atlas_shell_delegates_inspector_edit_analysis_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/InspectorEditAnalysisPanel\"" in source
    assert "<InspectorEditAnalysisPanel" in source


def test_atlas_shell_delegates_inspector_manage_nodes_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/InspectorManageNodesPanel\"" in source
    assert "<InspectorManageNodesPanel" in source


def test_atlas_shell_delegates_inspector_task_work_history_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/InspectorTaskWorkHistoryPanel\"" in source
    assert "<InspectorTaskWorkHistoryPanel" in source


def test_atlas_shell_delegates_inspector_alignment_panel_to_component() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/InspectorAlignmentPanel\"" in source
    assert "<InspectorAlignmentPanel" in source


def test_atlas_shell_uses_inspector_aux_data_hook() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/useInspectorAuxData\"" in source
    assert "} = useInspectorAuxData({" in source


def test_atlas_shell_uses_node_mutation_helpers_module() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/nodeMutation\"" in source
    assert "nodeTypeToPath(" in source
    assert "mutationNodeRef(" in source
    assert "createTypeLabel={" in source
    assert "nearestAncestorId(" in source


def test_atlas_shell_uses_inspector_details_helpers_module() -> None:
    source = _read(ATLAS_SHELL_PATH)

    assert "from \"@/components/atlas-shell/inspectorDetails\"" in source
    assert "selectedNodeDetails(selectedMeta, { formatOptionalDate, formatOptionalNumber })" in source
    assert "function selectedNodeDetails(meta: AtlasIndexNode)" not in source


def test_read_paths_use_no_store_cache_policy() -> None:
    function_sources = {
        "readAtlasSnapshot": _read(ATLAS_API_PATH),
        "readCyclesQuery": _read(ATLAS_API_PATH),
        "readBackendQuery": _read(ATLAS_API_PATH),
        "readLeadershipMetrics": _read(ATLAS_API_PATH),
        "readAdminAiHealth": _read(ADMIN_API_PATH),
        "readAdminPdfHealth": _read(ADMIN_API_PATH),
        "readAdminDbBackup": _read(ADMIN_API_PATH),
        "readBackendJob": _read(JOBS_API_PATH),
    }

    for function_name, source in function_sources.items():
        block = _function_block(source, function_name)
        assert 'cache: "no-store"' in block, f"Missing no-store for {function_name}"
