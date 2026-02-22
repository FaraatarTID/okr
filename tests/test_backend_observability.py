from fastapi.testclient import TestClient


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app)


def test_backend_generates_observability_headers(monkeypatch):
    client = _make_client(monkeypatch)

    response = client.get("/healthz")

    assert response.status_code == 200
    correlation_id = response.headers.get("X-Correlation-ID")
    request_id = response.headers.get("X-Request-ID")
    assert isinstance(correlation_id, str) and correlation_id.strip()
    assert isinstance(request_id, str) and request_id.strip()
    assert correlation_id == request_id


def test_backend_echoes_supplied_observability_headers(monkeypatch):
    client = _make_client(monkeypatch)

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
