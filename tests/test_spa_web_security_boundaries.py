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


def test_spa_web_backend_api_route_proxies_browser_requests_to_bff_only() -> None:
    route_source = _read(
        ROOT
        / "spa-web"
        / "src"
        / "app"
        / "api"
        / "backend"
        / "[...path]"
        / "route.ts"
    )
    assert "return proxyToBff(request, targetUrl)" in route_source
    assert "BFF_ORIGIN" in route_source

    helper_source = _read(ROOT / "spa-web" / "src" / "lib" / "bff-proxy.ts")
    assert "x-okr-actor" not in helper_source


def test_spa_web_next_config_does_not_use_backend_rewrite_proxy() -> None:
    next_config = _read(ROOT / "spa-web" / "next.config.ts")

    assert 'source: "/api/backend/:path*"' not in next_config
    assert "backend-api:8100" not in next_config


def test_spa_web_session_route_handlers_exist_and_proxy_to_bff() -> None:
    login_route = _read(
        ROOT / "spa-web" / "src" / "app" / "api" / "session" / "login" / "route.ts"
    )
    me_route = _read(
        ROOT / "spa-web" / "src" / "app" / "api" / "session" / "me" / "route.ts"
    )
    logout_route = _read(
        ROOT / "spa-web" / "src" / "app" / "api" / "session" / "logout" / "route.ts"
    )
    assert "/session/login" in login_route
    assert "/session/me" in me_route
    assert "/session/logout" in logout_route
    assert "BFF_ORIGIN" in login_route
    assert "BFF_ORIGIN" in me_route
    assert "BFF_ORIGIN" in logout_route
