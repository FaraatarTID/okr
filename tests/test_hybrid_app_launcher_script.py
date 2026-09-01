from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKER_LAUNCHER = ROOT / "scripts" / "windows" / "run_hybrid_app.bat"
LOCAL_LAUNCHER = ROOT / "scripts" / "windows" / "run_hybrid_app_local.bat"


def test_hybrid_launcher_exists_and_targets_spa_stack() -> None:
    payload = DOCKER_LAUNCHER.read_text(encoding="utf-8")

    assert "OKR Tracker - Hybrid SPA Launcher" in payload
    assert 'set "DOCKER_EXE="' in payload
    assert "compose version" in payload
    assert "scripts/check_deploy_config.py --mode runtime" in payload
    assert (
        'compose -f "%COMPOSE_FILE%" up -d --build backend-api backend-worker spa-bff spa-web'
        in payload
    )
    assert "http://127.0.0.1:3000" in payload


def test_local_hybrid_launcher_exists_and_starts_backend_bff_spa_without_docker() -> (
    None
):
    payload = LOCAL_LAUNCHER.read_text(encoding="utf-8")

    assert "OKR Tracker - Hybrid Local Launcher" in payload
    assert 'set "DOCKER_ENV_FILE=deploy\\docker\\.env"' in payload
    assert "Node.js v20+ is required." in payload
    assert 'set "LOG_DIR=%ROOT%tmp\\local-hybrid-logs"' in payload
    assert "Could not resolve a valid OKR_DATABASE_URL." in payload
    assert ":accept_db_url_if_valid" in payload
    assert "Ignoring DB URL from" in payload
    assert "Using OKR_DATABASE_URL from" in payload
    assert 'set "ROOT_CLEAN=%ROOT%"' in payload
    assert 'if "%ROOT_CLEAN:~-1%"=="\\" set "ROOT_CLEAN=%ROOT_CLEAN:~0,-1%"' in payload
    assert 'set "SPAWN_CWD=%ROOT_CLEAN%"' in payload
    assert 'set "SPAWN_EXE=%PYEXE%"' in payload
    assert 'set "SPAWN_ARGS=-m backend_app.run_api"' in payload
    assert 'set "SPAWN_ARGS=-m backend_app.worker"' in payload
    assert 'set "SPAWN_CWD=%ROOT_CLEAN%\\spa-bff"' in payload
    assert 'set "SPAWN_ARGS=/d /c npm run dev"' in payload
    assert 'set "SPAWN_CWD=%ROOT_CLEAN%\\spa-web"' in payload
    assert 'set "SPAWN_ARGS=/d /c npm run start -- -p 3000 -H 127.0.0.1"' in payload
    assert ":spawn_with_logs" in payload
    assert "Start-Process -FilePath $exe" in payload
    assert "Clearing stale Next.js cache" in payload
    assert "Building spa-web production bundle" in payload
    assert ":stop_stale_hybrid_processes" in payload
    assert ":spawn_backend_failed" in payload
    assert ":spawn_worker_failed" in payload
    assert ":spawn_bff_failed" in payload
    assert ":spawn_spa_failed" in payload
    assert "python -m venv" in payload
    assert "backend_app\\requirements.txt" in payload
    assert 'call npm --prefix "%ROOT%spa-bff" install' in payload
    assert 'call npm --prefix "%ROOT%spa-web" install' in payload
    assert 'set "OKR_BACKEND_API_URL=http://127.0.0.1:8100"' in payload
    assert "Failed to launch Backend API process." in payload
    assert "Failed to launch Backend Worker process." in payload
    assert "Failed to launch SPA BFF process." in payload
    assert "Failed to launch SPA Web process." in payload
    assert ":wait_for_http" in payload
    assert ":wait_for_worker" in payload
    assert "Still waiting for %SERVICE_NAME%" in payload
    assert "Invoke-WebRequest" in payload
    assert ":startup_failed" in payload
    assert "http://127.0.0.1:3000" in payload
