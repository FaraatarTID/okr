from fastapi.testclient import TestClient
from fastapi import HTTPException


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


def _with_dbless_admin_gate(monkeypatch, admin_user: str = "admin") -> None:
    """
    Make admin-gate checks deterministic in tests that do not need real DB lookups.
    """

    import backend_app.main as backend_main

    def _require_admin_actor_scope(actor: str | None) -> None:
        if str(actor or "").strip() != admin_user:
            raise HTTPException(status_code=403, detail="Admin access required.")

    monkeypatch.setattr(
        backend_main, "_require_admin_actor_scope", _require_admin_actor_scope
    )


def test_backend_generates_observability_headers(monkeypatch):
    client, _backend_main = _make_client(monkeypatch)

    response = client.get("/healthz")

    assert response.status_code == 200
    correlation_id = response.headers.get("X-Correlation-ID")
    request_id = response.headers.get("X-Request-ID")
    assert isinstance(correlation_id, str) and correlation_id.strip()
    assert isinstance(request_id, str) and request_id.strip()
    assert correlation_id == request_id


def test_backend_echoes_supplied_observability_headers(monkeypatch):
    client, _backend_main = _make_client(monkeypatch)

    response = client.get(
        "/healthz",
        headers={
            "X-Correlation-ID": "corr-123",
            "X-Request-ID": "req-456",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == "corr-123"
    assert response.headers.get("X-Request-ID") == "req-456"


def test_backend_admin_observability_metrics_requires_admin_gate(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    _with_dbless_admin_gate(monkeypatch, admin_user="admin")

    response = client.get(
        "/v1/admin/observability/metrics",
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 403


def test_backend_admin_observability_metrics_endpoint(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    _with_dbless_admin_gate(monkeypatch, admin_user="admin")
    monkeypatch.setattr(backend_main, "_require_admin_actor_scope", lambda _actor: None)

    baseline = client.get(
        "/v1/admin/observability/metrics",
        headers={"X-OKR-Actor": "admin"},
    ).json()
    baseline_requests = int(baseline.get("requests", {}).get("total_requests", 0) or 0)

    response = client.get(
        "/healthz",
        headers={"X-OKR-Actor": "admin"},
    )
    assert response.status_code == 200

    after = client.get(
        "/v1/admin/observability/metrics",
        headers={"X-OKR-Actor": "admin"},
    ).json()
    assert after["requests"]["total_requests"] >= baseline_requests + 2
    by_route = {
        item.get("route"): item.get("requests", 0)
        for item in after.get("requests", {}).get("by_route", [])
    }
    assert "GET /v1/admin/observability/metrics" in by_route
    assert "GET /healthz" in by_route
