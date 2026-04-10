from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATLAS_SHELL_PATH = ROOT / "spa-web" / "src" / "components" / "AtlasShell.tsx"
ATLAS_MODE_DATA_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useAtlasModeData.ts"
ATLAS_TIMER_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useTimerSession.ts"
ATLAS_INSPECTOR_NODE_ACTIONS_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useInspectorNodeActions.ts"
ATLAS_RITUAL_ACTIONS_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useRitualActions.ts"
ATLAS_ADMIN_ACTIONS_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useAdminActions.ts"
ATLAS_ADMIN_RESOURCES_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useAdminResources.ts"
ATLAS_MODE_ACTIONS_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useModeActions.ts"
ATLAS_MINDMAP_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useMindmapData.ts"
ATLAS_AUTH_BOOTSTRAP_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useAuthBootstrap.ts"
ATLAS_SNAPSHOT_LIFECYCLE_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useSnapshotLifecycle.ts"
ATLAS_DEEPLINK_CYCLE_BOOTSTRAP_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useDeepLinkCycleBootstrap.ts"
ATLAS_NAVIGATION_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useAtlasNavigation.ts"
ATLAS_SELECTION_FOCUS_SYNC_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useSelectionFocusSync.ts"
ATLAS_SHELL_ACCESS_CONTROL_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useShellAccessControl.ts"
ATLAS_MODE_STATE_RESET_HOOK_PATH = ROOT / "spa-web" / "src" / "components" / "atlas-shell" / "useModeStateReset.ts"
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
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_MODE_DATA_HOOK_PATH)
    timer_hook_source = _read(ATLAS_TIMER_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useAtlasModeData\"" in shell_source
    assert "} = useAtlasModeData({" in shell_source
    assert "const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;" in hook_source
    assert 'mode !== "dashboard" && mode !== "timeline"' in hook_source
    assert "window.setInterval(refreshFromSignal, DASHBOARD_REFRESH_INTERVAL_MS)" in hook_source
    assert 'window.addEventListener("focus", refreshFromSignal)' in hook_source
    assert 'document.addEventListener("visibilitychange", refreshFromSignal)' in hook_source
    assert "from \"@/components/atlas-shell/useTimerSession\"" in shell_source
    assert timer_hook_source.count("await refreshDashboardModeData(user, mode);") >= 2


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


def test_atlas_shell_uses_ritual_actions_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_RITUAL_ACTIONS_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useRitualActions\"" in shell_source
    assert "} = useRitualActions({" in shell_source
    assert "handleRitualCheckInSubmit" in hook_source
    assert "handleRitualExperimentCreate" in hook_source
    assert "handleRitualExperimentStart" in hook_source
    assert "handleRitualExperimentClose" in hook_source


def test_atlas_shell_uses_admin_actions_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_ADMIN_ACTIONS_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useAdminActions\"" in shell_source
    assert "} = useAdminActions({" in shell_source
    assert "handleAdminCreateUser" in hook_source
    assert "handleAdminCreateTeam" in hook_source
    assert "handleAdminCreateCycle" in hook_source
    assert "handleAdminBackupRestore" in hook_source


def test_atlas_shell_uses_admin_resources_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_ADMIN_RESOURCES_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useAdminResources\"" in shell_source
    assert "} = useAdminResources()" in shell_source
    assert "loadAdminResources(" in hook_source
    assert "loadAdminHealth(" in hook_source


def test_atlas_shell_uses_mode_actions_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_MODE_ACTIONS_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useModeActions\"" in shell_source
    assert "} = useModeActions({" in shell_source
    assert "handleWeeklyPlanSave" in hook_source
    assert "handleRetroCreate" in hook_source


def test_atlas_shell_uses_mindmap_data_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_MINDMAP_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useMindmapData\"" in shell_source
    assert "} = useMindmapData({ user, selectedMeta })" in shell_source
    assert "kind: \"mindmap.root\"" in hook_source


def test_atlas_shell_uses_auth_bootstrap_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_AUTH_BOOTSTRAP_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useAuthBootstrap\"" in shell_source
    assert "useAuthBootstrap()" in shell_source
    assert "readSessionUser" in hook_source
    assert "readSpaRolloutConfig" in hook_source


def test_atlas_shell_uses_snapshot_lifecycle_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_SNAPSHOT_LIFECYCLE_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useSnapshotLifecycle\"" in shell_source
    assert "} = useSnapshotLifecycle({" in shell_source
    assert "loadSnapshotForUser" in hook_source
    assert "window.setInterval" in hook_source


def test_atlas_shell_uses_deeplink_cycle_bootstrap_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_DEEPLINK_CYCLE_BOOTSTRAP_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useDeepLinkCycleBootstrap\"" in shell_source
    assert "useDeepLinkCycleBootstrap({" in shell_source
    assert "parseDeepLink" in hook_source
    assert "readCyclesQuery" in hook_source


def test_atlas_shell_uses_navigation_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_NAVIGATION_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useAtlasNavigation\"" in shell_source
    assert "} = useAtlasNavigation({" in shell_source
    assert "onOpenTaskInAtlas={handleOpenTaskInAtlas}" in shell_source
    assert "handleSidebarModeSelect" in hook_source
    assert "handleOpenTaskInAtlas" in hook_source


def test_atlas_shell_uses_selection_focus_sync_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_SELECTION_FOCUS_SYNC_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useSelectionFocusSync\"" in shell_source
    assert "useSelectionFocusSync({" in shell_source
    assert "atlasRuntime" in hook_source
    assert "selectedMeta?.type === \"TASK\"" in hook_source
    assert "setCreateDraft((prev) =>" in hook_source


def test_atlas_shell_uses_shell_access_control_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_SHELL_ACCESS_CONTROL_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useShellAccessControl\"" in shell_source
    assert "useShellAccessControl({" in shell_source
    assert "authHydrated" in hook_source
    assert "loadAdminHealth(user, false)" in hook_source
    assert "handleSignOut" in hook_source


def test_atlas_shell_uses_mode_state_reset_hook() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_MODE_STATE_RESET_HOOK_PATH)

    assert "from \"@/components/atlas-shell/useModeStateReset\"" in shell_source
    assert "useModeStateReset({" in shell_source
    assert "mode !== \"timeline\"" in hook_source
    assert "mode !== \"daily\"" in hook_source
    assert "mode !== \"ritual\"" in hook_source


def test_atlas_shell_uses_node_mutation_helpers_module() -> None:
    shell_source = _read(ATLAS_SHELL_PATH)
    hook_source = _read(ATLAS_INSPECTOR_NODE_ACTIONS_HOOK_PATH)

    assert "from \"@/components/atlas-shell/nodeMutation\"" in shell_source
    assert "from \"@/components/atlas-shell/useInspectorNodeActions\"" in shell_source
    assert "} = useInspectorNodeActions({" in shell_source
    assert "createTypeLabel={" in shell_source
    assert "nearestAncestorId(" in shell_source
    assert "nodeTypeToPath(" in hook_source
    assert "mutationNodeRef(" in hook_source


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
