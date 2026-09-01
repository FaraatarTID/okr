from __future__ import annotations

from pathlib import Path

from scripts import verify_deploy_readiness


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "docker" / "docker-compose.yml"


def _service_block(service: str, next_service: str | None = None) -> str:
    compose = COMPOSE.read_text(encoding="utf-8")
    block = compose.split(f"  {service}:", 1)[1]
    if next_service is not None:
        block = block.split(f"  {next_service}:", 1)[0]
    return block


def test_compose_keeps_api_worker_and_bff_as_independent_processes() -> None:
    api = _service_block("backend-api", "backend-worker")
    worker = _service_block("backend-worker", "spa-bff")
    bff = _service_block("spa-bff", "spa-web")

    assert 'python -m backend_app.run_api' in api
    assert 'python -m backend_app.worker' in worker
    assert 'dockerfile: spa-bff/Dockerfile' in bff
    assert 'restart: unless-stopped' in api
    assert 'restart: unless-stopped' in worker
    assert 'restart: unless-stopped' in bff
    assert 'healthcheck:' in api
    assert 'healthcheck:\n      disable: true' in worker


def test_readiness_requires_api_worker_bff_and_web(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
        calls.append(args)
        return 0, "backend-api\nbackend-worker\nspa-bff\nspa-web\n"

    monkeypatch.setattr(verify_deploy_readiness, "_run_command", fake_run)

    assert verify_deploy_readiness._check_compose_services(
        compose_file=COMPOSE,
        required_services=("backend-api", "backend-worker", "spa-bff", "spa-web"),
        timeout_seconds=1,
        interval_seconds=0.25,
    )
    assert calls
    assert "--filter" in calls[0]
    assert "status=running" in calls[0]
