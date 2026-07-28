from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import verify_resilience


def test_smoke_environment_reaches_pytest_without_losing_activation(
    tmp_path: Path,
) -> None:
    smoke_env, service_urls = verify_resilience._write_smoke_env_file(
        tmp_path / "smoke.env"
    )

    pytest_env = verify_resilience._build_smoke_pytest_env(
        smoke_env,
        service_urls,
    )

    assert pytest_env["TOP10_SMOKE"] == "1"
    assert pytest_env["TOP10_SMOKE_USERNAME"] == "admin"
    assert pytest_env["TOP10_SMOKE_PASSWORD"] == smoke_env[
        "OKR_BOOTSTRAP_ADMIN_PASSWORD"
    ]
    assert pytest_env["TOP10_SMOKE_BFF_URL"].endswith(service_urls["bff_port"])
    assert pytest_env["TOP10_SMOKE_WEB_URL"].endswith(service_urls["web_port"])
    assert smoke_env["OKR_POSTGRES_PASSWORD"] in smoke_env["OKR_DATABASE_URL"]
    assert "@postgres:5432/okr" in smoke_env["OKR_DATABASE_URL"]


def test_compose_process_environment_is_isolated_from_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "smoke.env"
    env_file.write_text(
        "OKR_DATABASE_URL=postgresql://smoke@postgres/okr\n"
        "BFF_SESSION_SECRET=smoke-session\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OKR_DATABASE_URL", "postgresql://ci-secret@external/okr")
    monkeypatch.setenv("SUPABASE_URL", "https://ci.example.invalid")
    monkeypatch.setenv("DOCKER_HOST", "docker-runner")
    captured: dict[str, object] = {}

    def _capture_run(argv, *, cwd, env=None):
        captured.update(argv=argv, cwd=cwd, env=env)
        return 0, ""

    monkeypatch.setattr(verify_resilience, "_run_command", _capture_run)

    verify_resilience._run_compose(
        compose_file=Path("compose.yml"),
        env_file=env_file,
        compose_project="smoke-project",
        command=["config"],
    )

    compose_env = captured["env"]
    assert isinstance(compose_env, dict)
    assert compose_env["OKR_DATABASE_URL"] == "postgresql://smoke@postgres/okr"
    assert compose_env["BFF_SESSION_SECRET"] == "smoke-session"
    assert "SUPABASE_URL" not in compose_env
    assert compose_env["DOCKER_HOST"] == "docker-runner"


def test_compose_diagnostics_redact_generated_credentials(monkeypatch) -> None:
    secret = "generated-sensitive-value"

    monkeypatch.setattr(
        verify_resilience,
        "_run_compose",
        lambda **_kwargs: (1, f"startup failed with {secret}"),
    )

    diagnostics = verify_resilience._compose_failure_diagnostics(
        compose_file=Path("compose.yml"),
        env_file=Path("smoke.env"),
        compose_project="smoke-project",
        secret_values=(secret,),
    )

    assert secret not in diagnostics
    assert diagnostics.count("[REDACTED]") == 2
    assert "docker compose ps (exit=1)" in diagnostics
    assert "docker compose logs (exit=1)" in diagnostics


def test_compose_up_failure_collects_diagnostics_and_cleans_up(
    monkeypatch,
    tmp_path: Path,
) -> None:
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def _fake_run_compose(*, command, **_kwargs):
        normalized = tuple(command)
        commands.append(normalized)
        if normalized[0] == "up":
            return 1, "backend-api became unhealthy"
        if normalized[0] == "ps":
            return 0, "backend-api unhealthy"
        if normalized[0] == "logs":
            return 0, "backend traceback"
        return 0, ""

    monkeypatch.setattr(
        verify_resilience,
        "_run_compose",
        _fake_run_compose,
    )

    result = verify_resilience._run_smoke_compose(
        args=SimpleNamespace(
            compose_file=compose_file,
            compose_project="smoke-project",
        )
    )

    assert result.status == "fail"
    assert "backend traceback" in result.detail
    assert any(command[0] == "ps" for command in commands)
    assert any(command[0] == "logs" for command in commands)
    assert any(command[0] == "down" for command in commands)
