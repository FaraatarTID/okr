from __future__ import annotations

from unittest.mock import MagicMock

from scripts import check_local_smoke_readiness


def test_check_docker_daemon_reports_permission_hints(monkeypatch) -> None:
    monkeypatch.setattr(check_local_smoke_readiness.shutil, "which", lambda name: "C:\\Docker\\docker.exe" if name == "docker" else None)

    mock_completed = MagicMock()
    mock_completed.returncode = 1
    mock_completed.stdout = ""
    mock_completed.stderr = "error during connect: Get \\\"npipe:////./pipe/docker_engine\\\": open C:\\\\Users\\\\me\\\\.docker\\\\config.json: Access is denied."

    monkeypatch.setattr(
        check_local_smoke_readiness.subprocess,
        "run",
        lambda *_, **__: mock_completed,
    )

    result = check_local_smoke_readiness._check_docker_daemon()

    assert not result.passed
    assert result.name == "Docker daemon"
    assert "permission is denied" in result.details.lower()
    assert "start docker desktop" in result.details.lower()
    assert "reopen this shell" in result.details.lower()


def test_check_docker_daemon_reports_not_available_without_permission_text(monkeypatch) -> None:
    monkeypatch.setattr(check_local_smoke_readiness.shutil, "which", lambda name: "C:\\Docker\\docker.exe" if name == "docker" else None)

    mock_completed = MagicMock()
    mock_completed.returncode = 1
    mock_completed.stdout = ""
    mock_completed.stderr = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?"

    monkeypatch.setattr(
        check_local_smoke_readiness.subprocess,
        "run",
        lambda *_, **__: mock_completed,
    )

    result = check_local_smoke_readiness._check_docker_daemon()

    assert not result.passed
    assert "daemon is not available" in result.details
