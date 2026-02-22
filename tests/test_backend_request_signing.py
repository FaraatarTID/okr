import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient


def _sign_request(*, secret: str, method: str, path: str, timestamp: str, nonce: str, body: bytes) -> str:
    body_digest = hashlib.sha256(body or b"").hexdigest()
    payload = "\n".join(
        [
            str(method).upper(),
            path,
            timestamp,
            nonce,
            body_digest,
        ]
    )
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _make_client(monkeypatch):
    import backend_app.main as backend_main
    import backend_app.security as backend_security

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "test-signing-secret")
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
        ),
    )
    return TestClient(backend_main.app)


def test_signed_request_is_accepted(monkeypatch):
    client = _make_client(monkeypatch)
    secret = "test-signing-secret"

    payload = {"task_id": 42, "user_id": "alice"}
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = "nonce-a1"
    signature = _sign_request(
        secret=secret,
        method="POST",
        path="/v1/timer/start",
        timestamp=timestamp,
        nonce=nonce,
        body=body,
    )

    response = client.post(
        "/v1/timer/start",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-OKR-Actor": "alice",
            "X-OKR-Timestamp": timestamp,
            "X-OKR-Nonce": nonce,
            "X-OKR-Signature": signature,
        },
    )
    assert response.status_code == 200
    assert int(response.json()["task_id"]) == 42


def test_replay_nonce_is_rejected(monkeypatch):
    client = _make_client(monkeypatch)
    secret = "test-signing-secret"

    payload = {"task_id": 7, "user_id": "alice"}
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = "nonce-replay-1"
    signature = _sign_request(
        secret=secret,
        method="POST",
        path="/v1/timer/start",
        timestamp=timestamp,
        nonce=nonce,
        body=body,
    )
    headers = {
        "Content-Type": "application/json",
        "X-OKR-Actor": "alice",
        "X-OKR-Timestamp": timestamp,
        "X-OKR-Nonce": nonce,
        "X-OKR-Signature": signature,
    }

    first = client.post("/v1/timer/start", content=body, headers=headers)
    second = client.post("/v1/timer/start", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 401
    assert "replay" in str(second.json().get("detail", "")).lower()


def test_missing_signature_headers_are_rejected(monkeypatch):
    client = _make_client(monkeypatch)

    response = client.post(
        "/v1/timer/start",
        json={"task_id": 12, "user_id": "alice"},
        headers={"X-OKR-Actor": "alice"},
    )
    assert response.status_code == 401


def test_production_requires_distributed_security_state_backend(monkeypatch):
    import backend_app.main as backend_main
    import backend_app.security as backend_security

    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "database")
    monkeypatch.delenv("OKR_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    backend_security._reset_security_state_for_tests()

    client = TestClient(backend_main.app)

    payload = {"task_id": 9, "user_id": "alice"}
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = "nonce-prod-db-required"
    signature = _sign_request(
        secret="test-signing-secret",
        method="POST",
        path="/v1/timer/start",
        timestamp=timestamp,
        nonce=nonce,
        body=body,
    )

    response = client.post(
        "/v1/timer/start",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-OKR-Actor": "alice",
            "X-OKR-Timestamp": timestamp,
            "X-OKR-Nonce": nonce,
            "X-OKR-Signature": signature,
        },
    )
    assert response.status_code == 503
    assert "security state backend" in str(response.json().get("detail", "")).lower()
