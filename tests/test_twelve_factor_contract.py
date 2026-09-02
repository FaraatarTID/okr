from __future__ import annotations

from pathlib import Path

from scripts.verify_twelve_factor_contract import verify_repository


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _valid_repository(root: Path) -> None:
    _write(root, "pyproject.toml", "[project]\ndependencies = []\n")
    _write(root, "uv.lock", "version = 1\n")
    _write(root, "package.json", '{"private": true}\n')
    _write(root, "package-lock.json", '{"lockfileVersion": 3}\n')
    _write(root, "spa-bff/package.json", '{"private": true}\n')
    _write(root, "spa-bff/package-lock.json", '{"lockfileVersion": 3}\n')
    _write(root, "spa-web/package.json", '{"private": true}\n')
    _write(root, "spa-web/package-lock.json", '{"lockfileVersion": 3}\n')
    _write(root, "deploy/docker/.env.example", "OKR_DATABASE_URL=\nBFF_SESSION_SECRET=\n")
    _write(root, "deploy/docker/.env.saas.example", "OKR_DATABASE_URL=\nOKR_BACKEND_SERVICE_TOKEN=\n")
    _write(
        root,
        "deploy/docker/docker-compose.yml",
        """
services:
  api:
    image: ${OKR_RELEASE_BACKEND_IMAGE:?required}
    environment:
      - OKR_DATABASE_URL=${OKR_DATABASE_URL:?required}
    ports:
      - "127.0.0.1:8100:8100"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/healthz"]
""",
    )
    _write(root, "deploy/docker/Dockerfile", "EXPOSE 8100\nHEALTHCHECK CMD curl -f http://localhost:8100/healthz\n")
    _write(root, "spa-bff/Dockerfile", "EXPOSE 3001\n")
    _write(root, "spa-web/Dockerfile", "EXPOSE 3000\n")
    _write(
        root,
        "deploy/docker/docker-compose.release.yml",
        "\n".join(
            f"image: ${{{name}:?required}}"
            for name in (
                "OKR_RELEASE_BACKEND_IMAGE",
                "OKR_RELEASE_BFF_IMAGE",
                "OKR_RELEASE_WEB_IMAGE",
            )
        ),
    )
    _write(root, ".github/workflows/promote-production.yml", "image@sha256:${DIGEST}\nrelease_sha: ${{ inputs.release_sha }}\n")
    _write(root, ".github/workflows/docker-deploy.yml", "sha256:[0-9a-fA-F]{64}\n")
    _write(root, "docs/saas/prerelease-runbook.md", "Run this one-off admin command:\n\n    alembic upgrade head\n")


def test_valid_repository_passes() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _valid_repository(root)
        assert verify_repository(root) == []


def test_missing_lockfile_is_reported_without_file_contents(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    (tmp_path / "uv.lock").unlink()

    failures = verify_repository(tmp_path)

    assert any("dependency lockfiles" in failure for failure in failures)
    assert all("OKR_DATABASE_URL" not in failure for failure in failures)


def test_non_immutable_promotion_reference_is_reported(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    (tmp_path / ".github/workflows/promote-production.yml").write_text(
        "image: ghcr.io/example/okr:latest\n", encoding="utf-8"
    )

    failures = verify_repository(tmp_path)

    assert any("immutable image references" in failure for failure in failures)


def test_release_image_inputs_require_workflow_digest_validation(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    _write(
        tmp_path,
        ".github/workflows/docker-deploy.yml",
        "image validation sha256:[0-9a-fA-F]{64}\n",
    )
    overlay = tmp_path / "deploy/docker/docker-compose.release.yml"
    overlay.write_text(
        "\n".join(
            f"image: ${{{name}:?required}}"
            for name in (
                "OKR_RELEASE_BACKEND_IMAGE",
                "OKR_RELEASE_BFF_IMAGE",
                "OKR_RELEASE_WEB_IMAGE",
            )
        ),
        encoding="utf-8",
    )

    assert verify_repository(tmp_path) == []


def test_release_image_inputs_without_digest_validation_are_reported(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    _write(
        tmp_path,
        "deploy/docker/docker-compose.release.yml",
        "image: ${OKR_RELEASE_BACKEND_IMAGE:?required}\n"
        "image: ${OKR_RELEASE_BFF_IMAGE:?required}\n"
        "image: ${OKR_RELEASE_WEB_IMAGE:?required}\n",
    )
    _write(tmp_path, ".github/workflows/docker-deploy.yml", "required image inputs\n")

    failures = verify_repository(tmp_path)

    assert any("sha256 image digest syntax" in failure for failure in failures)


def test_web_mapping_must_target_configured_container_port(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    compose = tmp_path / "deploy/docker/docker-compose.yml"
    compose.write_text(
        (compose.read_text(encoding="utf-8")
         + "\n  spa-web:\n"
         + "    ports:\n"
         + '      - "${SPA_WEB_HOST_PORT:-3000}:3000"\n'),
        encoding="utf-8",
    )

    failures = verify_repository(tmp_path)

    assert any("spa-web port mapping" in failure for failure in failures)


def test_missing_healthcheck_and_admin_command_are_reported(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    compose = tmp_path / "deploy/docker/docker-compose.yml"
    compose.write_text("services:\n  api:\n    ports: ['8100:8100']\n", encoding="utf-8")
    (tmp_path / "deploy/docker/Dockerfile").write_text("EXPOSE 8100\n", encoding="utf-8")
    (tmp_path / "docs/saas/prerelease-runbook.md").write_text(
        "Use the admin console.\n", encoding="utf-8"
    )

    failures = verify_repository(tmp_path)

    assert any("healthchecks" in failure for failure in failures)
    assert any("one-off admin command" in failure for failure in failures)


def test_secret_like_values_are_not_echoed_in_failures(tmp_path: Path) -> None:
    _valid_repository(tmp_path)
    secret = "super-secret-value-123"
    (tmp_path / "deploy/docker/.env.example").write_text(
        f"OKR_BACKEND_SERVICE_TOKEN={secret}\n", encoding="utf-8"
    )

    failures = verify_repository(tmp_path)

    assert secret not in "\n".join(failures)
