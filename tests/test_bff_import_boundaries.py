from __future__ import annotations

from scripts import check_spa_bff_boundaries


def test_bff_rejects_cross_service_and_runtime_imports(tmp_path, monkeypatch):
    path = tmp_path / "spa-bff" / "src" / "server.ts"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                'import type { User } from "../../spa-web/src/types";',
                'import { createApp } from "../../backend_app/main";',
                'import postgres from "pg";',
            ]
        ),
        encoding="utf-8",
    )
    source = path.read_text(encoding="utf-8")
    errors = []
    for reference in check_spa_bff_boundaries._imports(source):
        errors.extend(
            check_spa_bff_boundaries._violations(
                path,
                reference,
                tmp_path,
                tmp_path / "spa-bff",
            )
        )

    assert any("spa-web" in error for error in errors)
    assert any("backend_app" in error for error in errors)
    assert any("pg" in error for error in errors)


def test_bff_allows_local_and_declared_transport_imports(tmp_path, monkeypatch):
    path = tmp_path / "spa-bff" / "src" / "server.ts"
    path.parent.mkdir(parents=True)
    path.write_text(
        'import Fastify from "fastify";\n'
        'import { signRequest } from "./auth/signing.js";\n',
        encoding="utf-8",
    )
    source = path.read_text(encoding="utf-8")
    errors = []
    for reference in check_spa_bff_boundaries._imports(source):
        errors.extend(
            check_spa_bff_boundaries._violations(
                path,
                reference,
                tmp_path,
                tmp_path / "spa-bff",
            )
        )

    assert errors == []


def test_bff_manifest_rejects_cross_boundary_runtime_dependencies(tmp_path):
    manifest = tmp_path / "package.json"
    manifest.write_text(
        '{"dependencies": {"fastify": "1", "pg": "1", "spa-web": "1", '
        '"okr-platform-workspace": "file:..", "openapi-typescript": "1"}}',
        encoding="utf-8",
    )

    errors = check_spa_bff_boundaries._manifest_violations(manifest)

    assert any("pg" in error for error in errors)
    assert any("spa-web" in error for error in errors)
    assert any("okr-platform-workspace" in error for error in errors)
    assert any("openapi-typescript" in error for error in errors)


def test_bff_manifest_allows_transport_and_development_dependencies(tmp_path):
    manifest = tmp_path / "package.json"
    manifest.write_text(
        '{"dependencies": {"fastify": "1"}, '
        '"devDependencies": {"openapi-typescript": "1"}}',
        encoding="utf-8",
    )

    assert check_spa_bff_boundaries._manifest_violations(manifest) == []
