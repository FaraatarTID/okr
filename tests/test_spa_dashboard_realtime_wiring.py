from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATLAS_SHELL_PATH = ROOT / "spa-web" / "src" / "components" / "AtlasShell.tsx"
API_LIB_PATH = ROOT / "spa-web" / "src" / "lib" / "api.ts"


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


def test_read_paths_use_no_store_cache_policy() -> None:
    source = _read(API_LIB_PATH)
    read_functions = (
        "readAtlasSnapshot",
        "readCyclesQuery",
        "readBackendQuery",
        "readLeadershipMetrics",
        "readAdminAiHealth",
        "readAdminPdfHealth",
        "readAdminDbBackup",
        "readBackendJob",
    )

    for function_name in read_functions:
        block = _function_block(source, function_name)
        assert 'cache: "no-store"' in block, f"Missing no-store for {function_name}"
