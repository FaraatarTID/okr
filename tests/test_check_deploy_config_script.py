from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_deploy_config.py"
)


def _run_checker(env_file: Path, secrets_file: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--env-file",
            str(env_file),
            "--secrets-file",
            str(secrets_file),
            "--mode",
            mode,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_env(
    path: Path,
    *,
    placeholder_values: bool,
    include_throttle_key: bool = True,
    security_state_backend: str = "database",
    security_state_redis_url: str = "",
) -> None:
    service_token = "CHANGE_ME_SHARED_TOKEN" if placeholder_values else "tok_live_123"
    signing_secret = "CHANGE_ME_SIGNING_SECRET" if placeholder_values else "sign_live_123"
    bootstrap_pw = "CHANGE_ME_BOOTSTRAP_PASSWORD" if placeholder_values else "Admin!Passw0rd"
    db_url = (
        "postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require"
        if placeholder_values
        else "postgresql+psycopg2://okr_app.myref:Sup3rSecret@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    pdf_key = "" if placeholder_values else "pdf_live_key_123"

    rows = [
        "PORT=8501",
        "HOST_PORT=8501",
        "BASE_URL_PATH=",
        f"OKR_DATABASE_URL={db_url}",
        "OKR_BACKEND_API_URL=http://backend-api:8100",
        f"OKR_BACKEND_SERVICE_TOKEN={service_token}",
        f"OKR_BACKEND_SIGNING_SECRET={signing_secret}",
        f"OKR_BOOTSTRAP_ADMIN_PASSWORD={bootstrap_pw}",
        "OKR_BACKEND_PROXY_MUTATIONS=true",
        f"OKR_BACKEND_SECURITY_STATE_BACKEND={security_state_backend}",
        f"OKR_BACKEND_SECURITY_STATE_REDIS_URL={security_state_redis_url}",
        "OKR_ALLOW_LOCAL_BACKEND_FALLBACK=false",
        "OKR_ENFORCE_STRONG_PASSWORD_POLICY=true",
        "PDF_METHOD=pdfshift",
        f"PDFSHIFT_API_KEY={pdf_key}",
        "OKR_STRICT_RUNTIME_PREFLIGHT=true",
    ]
    if include_throttle_key:
        rows.insert(10, "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN=false")

    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_secrets(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'pdfshift_api_key = ""',
                'PDF_METHOD = "pdfshift"',
                "",
                "[database]",
                'url = "postgresql+psycopg2://okr_app.PROJECT_REF:DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_template_mode_accepts_examples_with_secure_defaults(tmp_path: Path):
    env_file = tmp_path / ".env.example"
    secrets_file = tmp_path / "secrets.toml.example"
    _write_env(env_file, placeholder_values=True)
    _write_secrets(secrets_file)

    result = _run_checker(env_file, secrets_file, mode="template")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Deploy config check passed (mode=template)" in result.stdout


def test_template_mode_fails_when_required_key_is_missing(tmp_path: Path):
    env_file = tmp_path / ".env.example"
    secrets_file = tmp_path / "secrets.toml.example"
    _write_env(env_file, placeholder_values=True, include_throttle_key=False)
    _write_secrets(secrets_file)

    result = _run_checker(env_file, secrets_file, mode="template")

    assert result.returncode == 1
    assert "OKR_AUTH_ALLOW_THROTTLE_FAIL_OPEN" in result.stdout


def test_runtime_mode_rejects_placeholder_values(tmp_path: Path):
    env_file = tmp_path / ".env"
    secrets_file = tmp_path / "secrets.toml"
    _write_env(env_file, placeholder_values=True)
    _write_secrets(secrets_file)

    result = _run_checker(env_file, secrets_file, mode="runtime")

    assert result.returncode == 1
    assert "appears to be a placeholder" in result.stdout


def test_runtime_mode_passes_with_non_placeholder_values(tmp_path: Path):
    env_file = tmp_path / ".env"
    secrets_file = tmp_path / "secrets.toml"
    _write_env(env_file, placeholder_values=False)
    _write_secrets(secrets_file)

    result = _run_checker(env_file, secrets_file, mode="runtime")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Deploy config check passed (mode=runtime)" in result.stdout


def test_runtime_mode_rejects_redis_backend_without_redis_url(tmp_path: Path):
    env_file = tmp_path / ".env"
    secrets_file = tmp_path / "secrets.toml"
    _write_env(
        env_file,
        placeholder_values=False,
        security_state_backend="redis",
        security_state_redis_url="",
    )
    _write_secrets(secrets_file)

    result = _run_checker(env_file, secrets_file, mode="runtime")

    assert result.returncode == 1
    assert "OKR_BACKEND_SECURITY_STATE_REDIS_URL is required" in result.stdout


def test_runtime_mode_accepts_redis_backend_with_valid_redis_url(tmp_path: Path):
    env_file = tmp_path / ".env"
    secrets_file = tmp_path / "secrets.toml"
    _write_env(
        env_file,
        placeholder_values=False,
        security_state_backend="redis",
        security_state_redis_url="redis://redis.internal:6379/0",
    )
    _write_secrets(secrets_file)

    result = _run_checker(env_file, secrets_file, mode="runtime")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Deploy config check passed (mode=runtime)" in result.stdout
