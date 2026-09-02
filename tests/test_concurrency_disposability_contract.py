from __future__ import annotations

import signal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "docker" / "docker-compose.yml"


def test_worker_shutdown_signal_stops_polling_without_interrupting_current_job() -> None:
    from backend_app import worker

    worker.reset_shutdown_state()
    assert not worker.shutdown_requested()

    worker.request_shutdown(signal.SIGTERM, None)

    assert worker.shutdown_requested()
    assert worker.wait_for_shutdown_or_timeout(60) is True
    worker.reset_shutdown_state()


def test_api_worker_setting_is_environment_driven(monkeypatch) -> None:
    from backend_app import config

    monkeypatch.setenv("OKR_BACKEND_API_WORKERS", "3")
    settings = config.get_backend_settings()

    assert settings.api_workers == 3


def test_compose_declares_independent_scaling_and_single_job_worker_process() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "OKR_BACKEND_API_REPLICAS" in compose
    assert "OKR_BACKEND_WORKER_REPLICAS" in compose
    assert "SPA_BFF_REPLICAS" in compose
    assert "SPA_WEB_REPLICAS" in compose
    assert "OKR_BACKEND_API_WORKERS" in compose
    assert "deploy:\n      replicas: ${OKR_BACKEND_WORKER_REPLICAS:-1}" in compose
    assert "python -m backend_app.worker" in compose
    assert "--scale backend-worker=" in compose
    assert "stop_grace_period:" in compose


def test_job_claim_contract_remains_atomic_and_postgres_safe() -> None:
    source = (ROOT / "backend_app" / "jobs.py").read_text(encoding="utf-8")

    assert "with_for_update(skip_locked=True)" in source
    assert '.where(AsyncJob.status == AsyncJobStatus.PENDING)' in source
    assert "status=AsyncJobStatus.RUNNING" in source


def test_worker_has_bounded_shutdown_requeue_and_liveness_contract() -> None:
    worker = (ROOT / "backend_app" / "worker.py").read_text(encoding="utf-8")
    healthcheck = (ROOT / "backend_app" / "worker_healthcheck.py").read_text(
        encoding="utf-8"
    )
    compose = COMPOSE.read_text(encoding="utf-8")

    assert "requeue_job_for_shutdown" in worker
    assert "shutdown_requested()" in worker
    assert "write_heartbeat()" in worker
    assert "OKR_WORKER_HEARTBEAT_PATH" in healthcheck
    assert "python -m backend_app.worker_healthcheck" in compose
    assert "disable: true" not in compose
    assert "OKR_WORKER_SHUTDOWN_GRACE_SECONDS" in worker
    assert "terminationGracePeriodSeconds:" in (ROOT / "deploy/k8s/deployment-backend-worker.yaml").read_text(encoding="utf-8")
    assert "livenessProbe:" in (ROOT / "deploy/k8s/deployment-backend-worker.yaml").read_text(encoding="utf-8")
    assert "readinessProbe:" in (ROOT / "deploy/k8s/deployment-backend-worker.yaml").read_text(encoding="utf-8")
