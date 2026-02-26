from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient


def _make_client(monkeypatch, *, enforce_signing: bool) -> TestClient:
    import backend_app.main as backend_main
    import backend_app.security as backend_security

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", "svc-token-123")
    monkeypatch.setenv(
        "OKR_BACKEND_ENFORCE_REQUEST_SIGNING",
        "true" if enforce_signing else "false",
    )
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "signing-secret-123")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")

    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    backend_security._reset_security_state_for_tests()

    monkeypatch.setattr(
        backend_main,
        "start_timer",
        lambda task_id, actor: SimpleNamespace(
            id=1,
            task_id=task_id,
            start_time=datetime.now(timezone.utc).replace(tzinfo=None),
            actor=actor,
        ),
    )

    return TestClient(backend_main.app)


def _timer_start_payload() -> dict[str, object]:
    return {"task_id": 42, "user_id": "alice"}


def test_direct_backend_timer_start_without_service_token_is_rejected(monkeypatch) -> None:
    client = _make_client(monkeypatch, enforce_signing=False)

    response = client.post(
        "/v1/timer/start",
        json=_timer_start_payload(),
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 401
    assert "service token" in str(response.json().get("detail", "")).lower()


def test_direct_backend_timer_start_with_invalid_service_token_is_rejected(
    monkeypatch,
) -> None:
    client = _make_client(monkeypatch, enforce_signing=False)

    response = client.post(
        "/v1/timer/start",
        json=_timer_start_payload(),
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Service-Token": "invalid-token",
        },
    )

    assert response.status_code == 401
    assert "service token" in str(response.json().get("detail", "")).lower()


def test_internal_backend_timer_start_with_service_token_is_accepted(monkeypatch) -> None:
    client = _make_client(monkeypatch, enforce_signing=False)

    response = client.post(
        "/v1/timer/start",
        json=_timer_start_payload(),
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Service-Token": "svc-token-123",
        },
    )

    assert response.status_code == 200
    assert int(response.json()["task_id"]) == 42


def test_direct_unsigned_backend_call_is_rejected_when_signing_enabled(
    monkeypatch,
) -> None:
    client = _make_client(monkeypatch, enforce_signing=True)

    response = client.post(
        "/v1/timer/start",
        json=_timer_start_payload(),
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Service-Token": "svc-token-123",
        },
    )

    assert response.status_code == 401
    assert "signed request" in str(response.json().get("detail", "")).lower()
