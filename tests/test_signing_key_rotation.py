"""Tests for signing key rotation: key-ID header, overlap verification.

Covers:
- Advertised key ID requires x-okr-key-id on signed requests.
- Unknown key IDs are rejected.
- Signatures made with the previous secret verify during the overlap window.
- Literal "previous" key ID forces previous-secret verification.
- No advertised key ID preserves legacy (no header) behavior.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

_CURRENT_SECRET = "current-signing-secret-0123456789abcdef"
_PREVIOUS_SECRET = "previous-signing-secret-fedcba9876543210"


def _sign_request(
    *,
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    body_digest = hashlib.sha256(body or b"").hexdigest()
    payload = "\n".join([method.upper(), path, timestamp, nonce, body_digest])
    return hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _make_client(monkeypatch, *, advertise_key_id: bool = True) -> TestClient:
    import backend_app.main as backend_main
    import backend_app.security as backend_security

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", _CURRENT_SECRET)
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET_PREVIOUS", _PREVIOUS_SECRET)
    if advertise_key_id:
        monkeypatch.setenv("OKR_BACKEND_SIGNING_KEY_ID", "key-2026-08")
    else:
        monkeypatch.delenv("OKR_BACKEND_SIGNING_KEY_ID", raising=False)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    backend_security._reset_security_state_for_tests()
    monkeypatch.setattr(
        backend_main,
        "start_timer",
        lambda task_id, actor: SimpleNamespace(
            id=task_id,
            task_id=task_id,
            start_time=None,
        ),
    )
    return TestClient(backend_main.app)


def _signed_post(
    client: TestClient,
    *,
    secret: str,
    nonce: str,
    key_id: str | None = None,
    path: str = "/v1/timer/start",
) -> object:
    body = json.dumps({"task_id": 5}, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign_request(
        secret=secret, method="POST", path=path, timestamp=timestamp,
        nonce=nonce, body=body,
    )
    headers = {
        "Content-Type": "application/json",
        "X-OKR-Actor": "alice",
        "X-OKR-Timestamp": timestamp,
        "X-OKR-Nonce": nonce,
        "X-OKR-Signature": signature,
    }
    if key_id is not None:
        headers["X-OKR-Key-Id"] = key_id
    return client.post(path, content=body, headers=headers)


def test_current_key_with_matching_id_accepted(monkeypatch):
    client = _make_client(monkeypatch)
    response = _signed_post(
        client, secret=_CURRENT_SECRET, nonce="rot-n1", key_id="key-2026-08"
    )
    assert response.status_code == 200


def test_missing_key_id_rejected_when_advertised(monkeypatch):
    client = _make_client(monkeypatch)
    response = _signed_post(client, secret=_CURRENT_SECRET, nonce="rot-n2")
    assert response.status_code == 401
    assert "key ID" in response.json()["detail"]


def test_unknown_key_id_rejected(monkeypatch):
    client = _make_client(monkeypatch)
    response = _signed_post(
        client, secret=_CURRENT_SECRET, nonce="rot-n3", key_id="key-rogue"
    )
    assert response.status_code == 401
    assert "Unknown signing key ID" in response.json()["detail"]


def test_previous_secret_accepted_during_overlap(monkeypatch):
    """Signature made with the OLD secret verifies while overlap is configured."""
    client = _make_client(monkeypatch)
    response = _signed_post(
        client, secret=_PREVIOUS_SECRET, nonce="rot-n4", key_id="key-2026-08"
    )
    assert response.status_code == 200


def test_previous_key_id_forces_previous_secret_only(monkeypatch):
    client = _make_client(monkeypatch)
    # Current-secret signature with explicit "previous" ID must fail.
    response = _signed_post(
        client, secret=_CURRENT_SECRET, nonce="rot-n5", key_id="previous"
    )
    assert response.status_code == 401
    # Previous-secret signature with "previous" ID must pass.
    response = _signed_post(
        client, secret=_PREVIOUS_SECRET, nonce="rot-n6", key_id="previous"
    )
    assert response.status_code == 200


def test_no_advertised_key_id_preserves_legacy_behavior(monkeypatch):
    """Without an advertised key ID, unsigned-ID requests behave as before."""
    client = _make_client(monkeypatch, advertise_key_id=False)
    response = _signed_post(client, secret=_CURRENT_SECRET, nonce="rot-n7")
    assert response.status_code == 200


def test_wrong_secret_rejected_entirely(monkeypatch):
    client = _make_client(monkeypatch)
    response = _signed_post(
        client, secret="totally-wrong-secret", nonce="rot-n8", key_id="key-2026-08"
    )
    assert response.status_code == 401
