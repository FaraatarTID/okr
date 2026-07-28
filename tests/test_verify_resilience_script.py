from __future__ import annotations

from pathlib import Path

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
