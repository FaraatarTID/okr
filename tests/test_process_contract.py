"""Focused tests for the Twelve-Factor process contract verifier."""

from pathlib import Path

from scripts.verify_process_contract import verify_repository


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _valid_repository(tmp_path: Path) -> Path:
    compose = """
services:
  backend-api:
    environment:
      - OKR_BACKEND_PORT=${OKR_BACKEND_PORT:-8100}
    command: ["python", "-m", "backend_app.run_api"]
    ports:
      - "${OKR_BACKEND_HOST_PORT:-8100}:${OKR_BACKEND_PORT:-8100}"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:${OKR_BACKEND_PORT:-8100}/healthz"]
    restart: unless-stopped
  backend-worker:
    environment:
      - OKR_BACKEND_WORKER_POLL_SECONDS=${OKR_BACKEND_WORKER_POLL_SECONDS:-2}
    command: ["python", "-m", "backend_app.worker"]
    restart: unless-stopped
    healthcheck:
      disable: true
  spa-bff:
    environment:
      - BFF_PORT=${BFF_PORT:-3001}
    ports:
      - "${SPA_BFF_HOST_PORT:-3001}:${BFF_PORT:-3001}"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O - http://127.0.0.1:${BFF_PORT:-3001}/healthz"]
    restart: unless-stopped
  spa-web:
    environment:
      - PORT=${SPA_WEB_PORT:-3000}
    ports:
      - "${SPA_WEB_HOST_PORT:-3000}:${SPA_WEB_PORT:-3000}"
    restart: unless-stopped
  postgres:
    volumes:
      - okr-postgres-data:/var/lib/postgresql/data
volumes:
  okr-postgres-data:
"""
    _write(tmp_path, "deploy/docker/docker-compose.yml", compose)
    return tmp_path


def test_real_repository_process_contract_passes() -> None:
    failures = verify_repository(Path(__file__).resolve().parents[1])
    assert failures == []


def test_missing_process_contract_requirements_are_reported(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "deploy/docker/docker-compose.yml",
        """
services:
  backend-api:
    command: python -m backend_app.run_api
  backend-worker:
    command: python -m backend_app.run_api
""",
    )

    failures = verify_repository(tmp_path)

    assert any("environment-driven ports" in failure for failure in failures)
    assert any("health/readiness" in failure for failure in failures)
    assert any("restart/disposability" in failure for failure in failures)
    assert any("separate API and worker processes" in failure for failure in failures)
    assert any("database state volume" in failure for failure in failures)


def test_worker_without_healthcheck_is_valid_when_restart_is_configured(tmp_path: Path) -> None:
    root = _valid_repository(tmp_path)
    compose = (root / "deploy/docker/docker-compose.yml").read_text(encoding="utf-8")
    compose = compose.replace("    restart: unless-stopped\n    healthcheck:\n      disable: true", "    healthcheck:\n      disable: true")
    (root / "deploy/docker/docker-compose.yml").write_text(compose, encoding="utf-8")

    failures = verify_repository(root)

    assert any("restart/disposability" in failure for failure in failures)


def test_literal_web_process_port_is_not_environment_driven(tmp_path: Path) -> None:
    root = _valid_repository(tmp_path)
    compose_path = root / "deploy/docker/docker-compose.yml"
    compose = compose_path.read_text(encoding="utf-8").replace(
        "      - PORT=${SPA_WEB_PORT:-3000}",
        "      - PORT=3000",
    )
    compose_path.write_text(compose, encoding="utf-8")

    failures = verify_repository(root)

    assert any("environment-driven ports" in failure for failure in failures)


def test_local_control_plane_volume_is_rejected(tmp_path: Path) -> None:
    root = _valid_repository(tmp_path)
    compose_path = root / "deploy/docker/docker-compose.yml"
    compose = compose_path.read_text(encoding="utf-8").replace(
        "  backend-api:\n", "  backend-api:\n    volumes:\n      - okr-control-plane-state:/var/lib/okr\n"
    )
    compose_path.write_text(compose, encoding="utf-8")

    failures = verify_repository(root)

    assert any("process-local volume" in failure for failure in failures)


def test_runtime_template_cannot_enable_process_local_state(tmp_path: Path) -> None:
    root = _valid_repository(tmp_path)
    _write(
        root,
        "deploy/docker/.env.example",
        "OKR_CONTROL_PLANE_STATE_PATH=/var/lib/okr/state.json\n",
    )

    failures = verify_repository(root)

    assert any("normal runtime template enables process-local state" in failure for failure in failures)
