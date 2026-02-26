from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_compose_backend_api_defaults_to_loopback_bind_address() -> None:
    compose = _read("deploy/docker/docker-compose.yml")
    assert "${OKR_BACKEND_BIND_ADDRESS:-127.0.0.1}" in compose


def test_compose_spa_bff_defaults_to_loopback_bind_address() -> None:
    compose = _read("deploy/docker/docker-compose.yml")
    assert "${SPA_BFF_BIND_ADDRESS:-127.0.0.1}" in compose


def test_compose_spa_web_defaults_to_loopback_bind_address() -> None:
    compose = _read("deploy/docker/docker-compose.yml")
    assert "${SPA_WEB_BIND_ADDRESS:-127.0.0.1}" in compose


def test_nginx_templates_do_not_proxy_public_traffic_to_backend_api() -> None:
    nginx_default = _read("deploy/nginx.conf")
    nginx_company = _read("deploy/nginx.okr.mycompany.com.conf")
    for payload in (nginx_default, nginx_company):
        assert "backend-api" not in payload
        assert ":8100" not in payload
