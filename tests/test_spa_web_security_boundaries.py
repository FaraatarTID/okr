from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_FRONTEND_SECRET_KEYS = (
    "OKR_BACKEND_SERVICE_TOKEN",
    "OKR_BACKEND_SIGNING_SECRET",
    "NEXT_PUBLIC_OKR_BACKEND_SERVICE_TOKEN",
    "NEXT_PUBLIC_OKR_BACKEND_SIGNING_SECRET",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _spa_web_compose_block(compose_payload: str) -> str:
    matched = re.search(
        r"(?ms)^  spa-web:\n(.*?)(?:^  [a-zA-Z0-9_-]+:|\Z)",
        compose_payload,
    )
    assert matched is not None, "spa-web compose service block not found."
    return matched.group(1)


def test_spa_web_source_does_not_reference_backend_service_secret_keys() -> None:
    paths = [
        ROOT / "spa-web" / "next.config.ts",
        *sorted((ROOT / "spa-web" / "src").rglob("*.ts")),
        *sorted((ROOT / "spa-web" / "src").rglob("*.tsx")),
    ]
    assert paths

    for path in paths:
        payload = _read(path)
        for forbidden_key in FORBIDDEN_FRONTEND_SECRET_KEYS:
            assert forbidden_key not in payload, f"Forbidden key in {path}: {forbidden_key}"


def test_spa_web_compose_env_does_not_include_backend_service_secrets_or_direct_backend_url() -> None:
    compose = _read(ROOT / "deploy" / "docker" / "docker-compose.yml")
    spa_web_block = _spa_web_compose_block(compose)

    assert "OKR_BACKEND_SERVICE_TOKEN" not in spa_web_block
    assert "OKR_BACKEND_SIGNING_SECRET" not in spa_web_block
    assert "OKR_BACKEND_API_URL" not in spa_web_block


def test_spa_web_rewrite_routes_browser_requests_to_bff_only() -> None:
    next_config = _read(ROOT / "spa-web" / "next.config.ts")

    assert 'source: "/api/backend/:path*"' in next_config
    assert "destination: `${bffOrigin}/api/backend/:path*`" in next_config
    assert "backend-api:8100" not in next_config
