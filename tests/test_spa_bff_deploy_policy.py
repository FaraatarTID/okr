from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str | Path) -> str:
    target = Path(path)
    if target.is_absolute():
        return target.read_text(encoding="utf-8")
    return (ROOT / target).read_text(encoding="utf-8")


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


def test_k8s_backend_api_service_remains_internal() -> None:
    service = _read("deploy/k8s/service-backend-api.yaml")
    assert "type: ClusterIP" in service
    assert "type: NodePort" not in service
    assert "type: LoadBalancer" not in service
    assert "externalTrafficPolicy" not in service


def test_k8s_backend_api_deployment_has_no_public_host_exposure() -> None:
    deployment = _read("deploy/k8s/deployment-backend-api.yaml")
    assert "hostNetwork: true" not in deployment
    assert "nodePort" not in deployment
    assert "hostPort" not in deployment


def test_k8s_manifests_do_not_define_ingress_for_backend_api() -> None:
    manifests = (ROOT / "deploy" / "k8s").glob("*.yaml")
    assert all("kind: Ingress" not in _read(str(path)) for path in manifests)
