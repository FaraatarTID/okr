from fastapi import HTTPException
from pydantic import BaseModel
from fastapi.testclient import TestClient


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


def test_backend_error_envelope_for_missing_route_includes_request_ids(monkeypatch):
    client, _backend_main = _make_client(monkeypatch)
    route = "/__backend-error-envelope-route-not-found"
    if not any(
        getattr(route_obj, "path", "") == route for route_obj in _backend_main.app.router.routes
    ):

        def _not_found():
            raise HTTPException(status_code=404, detail="Resource not found.")

        _backend_main.app.get(route)(_not_found)

    response = client.get(route)

    payload = response.json()
    assert response.status_code == 404
    assert payload.get("code") == "HTTP_404"
    assert payload.get("request_id")
    assert payload.get("correlation_id")
    assert payload.get("message") == "Resource not found."
    assert payload.get("error")
    assert response.headers.get("X-Correlation-ID") == payload.get("correlation_id")
    assert response.headers.get("X-Request-ID") == payload.get("request_id")


def test_backend_request_validation_error_envelope(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    class EchoRequest(BaseModel):
        user_id: int

    route = "/__backend-error-envelope-validation"
    if not any(getattr(route_obj, "path", "") == route for route_obj in backend_main.app.router.routes):

        def _echo(payload: EchoRequest):
            return payload.dict()

        backend_main.app.post(route)(_echo)

    response = client.post(route, json={"user_id": "abc"})

    payload = response.json()
    assert response.status_code == 422
    assert payload.get("code") == "HTTP_422"
    assert payload.get("detail") is not None
    assert payload.get("message") == "Request failed."
    assert payload.get("request_id")
    assert payload.get("correlation_id")


def test_backend_generic_exception_error_envelope(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    route = "/__backend-error-envelope-generic"
    if not any(getattr(route_obj, "path", "") == route for route_obj in backend_main.app.router.routes):

        def _crash():
            raise RuntimeError("crash")

        backend_main.app.get(route)(_crash)

    response = client.get(route)

    payload = response.json()
    assert response.status_code == 500
    assert payload.get("code") == "HTTP_500"
    assert payload.get("message") == "Internal server error."
    assert payload.get("error") == "Internal server error."
    assert payload.get("request_id")
    assert payload.get("correlation_id")
