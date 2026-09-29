from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


SECRET = "t23-test-signing-secret"
TOKEN = "t23-test-service-token"


def _signature(
    method: str, path: str, body: bytes, timestamp: str, nonce: str, **extra
):
    parts = [method.upper(), path, timestamp, nonce, hashlib.sha256(body).hexdigest()]
    sid = extra.get("x_okr_session_id")
    actor = extra.get("x_okr_session_actor")
    if sid is not None or actor is not None:
        parts.extend(
            [
                f"session_id:{sid.encode().hex() if sid is not None else '-'}",
                f"session_actor:{actor.encode().hex() if actor is not None else '-'}",
            ]
        )
    return hmac.new(
        SECRET.encode(), "\n".join(parts).encode(), hashlib.sha256
    ).hexdigest()


def _request(client, method, path, *, body=b"", headers=None, nonce=None, **signed):
    timestamp = str(int(time.time()))
    request_headers = {
        "X-OKR-Service-Token": TOKEN,
        "X-OKR-Timestamp": timestamp,
        "X-OKR-Nonce": nonce or f"nonce-{time.time_ns()}",
        "Content-Type": "application/json",
    }
    request_headers.update(headers or {})
    request_headers["X-OKR-Signature"] = _signature(
        method,
        path,
        body,
        timestamp,
        request_headers["X-OKR-Nonce"],
        **signed,
    )
    return client.request(method, path, content=body, headers=request_headers)


@pytest.fixture
def client(monkeypatch):
    import backend_app.main as backend_main
    import backend_app.security as backend_security
    import backend_app.security_state as security_state

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", SECRET)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    backend_security._reset_security_state_for_tests()
    monkeypatch.setattr(
        backend_security,
        "_resolve_current_actor_scope",
        lambda actor, token_version: {
            "actor_id": 17,
            "actor_username": actor,
            "role": "member",
        },
    )
    timer_calls = []

    def start_timer(task_id, actor):
        timer_calls.append((task_id, actor))
        return SimpleNamespace(
            id=task_id,
            task_id=task_id,
            start_time=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(backend_main, "start_timer", start_timer)
    test_client = TestClient(backend_main.app)
    test_client.timer_calls = timer_calls
    yield test_client
    security_state.reset_security_state_for_tests()


def _session_request(client, *, sid="opaque-session", actor="17", nonce=None):
    body = json.dumps({"task_id": 2}, separators=(",", ":")).encode()
    return _request(
        client,
        "POST",
        "/v1/timer/start",
        body=body,
        nonce=nonce,
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Token-Version": "1",
            "X-OKR-Session-Id": sid,
            "X-OKR-Session-Actor": actor,
        },
        x_okr_session_id=sid,
        x_okr_session_actor=actor,
    )


def test_internal_registration_hashes_raw_session_id_and_protected_route_accepts(
    client,
):
    sid = "opaque-session-value-never-persisted"
    body = json.dumps(
        {
            "session_id": sid,
            "actor_id": 17,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    response = _request(
        client, "POST", "/v1/internal/session-registry/register", body=body
    )

    assert response.status_code == 200, response.text
    assert _session_request(client, sid=sid).status_code == 200


def test_internal_revoke_is_idempotent_and_rejects_following_request(client):
    sid = "revoke-through-service-route"
    register_body = json.dumps(
        {
            "session_id": sid,
            "actor_id": 17,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    assert (
        _request(
            client,
            "POST",
            "/v1/internal/session-registry/register",
            body=register_body,
        ).status_code
        == 200
    )
    revoke_body = json.dumps({"session_id": sid}, separators=(",", ":")).encode()
    assert (
        _request(
            client,
            "POST",
            "/v1/internal/session-registry/revoke",
            body=revoke_body,
        ).status_code
        == 200
    )
    assert (
        _request(
            client,
            "POST",
            "/v1/internal/session-registry/revoke",
            body=revoke_body,
        ).status_code
        == 200
    )
    assert _session_request(client, sid=sid).status_code == 401


@pytest.mark.parametrize(
    ("sid", "actor", "status"),
    [
        (None, "17", 401),
        ("opaque-session", None, 401),
        ("unknown-session-identifier", "17", 401),
        ("known-session-identifier", "99", 401),
    ],
)
def test_actor_route_rejects_missing_unknown_or_mismatched_registry_assertions(
    client, sid, actor, status
):
    from backend_app.security_state import register_session

    known_sid = "known-session-identifier"
    if sid in {known_sid, None}:
        register_session(
            session_digest=hashlib.sha256(known_sid.encode()).hexdigest(),
            actor_id="17",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    session_headers = {}
    signed = {}
    if sid is not None:
        session_headers["X-OKR-Session-Id"] = sid
        signed["x_okr_session_id"] = sid
    if actor is not None:
        session_headers["X-OKR-Session-Actor"] = actor
        signed["x_okr_session_actor"] = actor
    body = b'{"task_id":2}'
    response = _request(
        client,
        "POST",
        "/v1/timer/start",
        body=body,
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Token-Version": "1",
            **session_headers,
        },
        **signed,
    )
    assert response.status_code == status
    assert client.timer_calls == []


def test_modified_session_header_invalidates_signature_before_handler(client):
    sid = "signed-session"
    from backend_app.security_state import register_session

    register_session(
        session_digest=hashlib.sha256(sid.encode()).hexdigest(),
        actor_id="17",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    body = b'{"task_id":2}'
    timestamp = str(int(time.time()))
    nonce = "tampered-session-assertion"
    signature = _signature(
        "POST",
        "/v1/timer/start",
        body,
        timestamp,
        nonce,
        x_okr_session_id=sid,
        x_okr_session_actor="17",
    )
    response = client.post(
        "/v1/timer/start",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-OKR-Actor": "alice",
            "X-OKR-Token-Version": "1",
            "X-OKR-Session-Id": sid,
            "X-OKR-Session-Actor": "18",
            "X-OKR-Timestamp": timestamp,
            "X-OKR-Nonce": nonce,
            "X-OKR-Signature": signature,
            "X-OKR-Service-Token": TOKEN,
        },
    )
    assert response.status_code == 401
    assert client.timer_calls == []


def test_noncanonical_whitespace_in_session_assertions_is_rejected(client):
    sid = "canonical-whitespace-session-id"
    from backend_app.security_state import register_session

    register_session(
        session_digest=hashlib.sha256(sid.encode()).hexdigest(),
        actor_id="17",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    body = b'{"task_id":2}'
    for index, (sent_sid, sent_actor) in enumerate([(sid + " ", "17"), (sid, "17 ")]):
        for mode, signed_sid, signed_actor in (
            ("tampered", sid, "17"),
            ("raw", sent_sid, sent_actor),
        ):
            timestamp = str(int(time.time()))
            nonce = f"noncanonical-session-assertion-{index}-{mode}"
            signature = _signature(
                "POST",
                "/v1/timer/start",
                body,
                timestamp,
                nonce,
                x_okr_session_id=signed_sid,
                x_okr_session_actor=signed_actor,
            )
            response = client.post(
                "/v1/timer/start",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-OKR-Actor": "alice",
                    "X-OKR-Token-Version": "1",
                    "X-OKR-Session-Id": sent_sid,
                    "X-OKR-Session-Actor": sent_actor,
                    "X-OKR-Timestamp": timestamp,
                    "X-OKR-Nonce": nonce,
                    "X-OKR-Signature": signature,
                    "X-OKR-Service-Token": TOKEN,
                },
            )
            assert response.status_code == 401
    assert client.timer_calls == []


def test_payload_actor_without_signed_header_actor_is_rejected_before_handler(client):
    sid = "actorless-payload-session-binding"
    from backend_app.security_state import register_session

    register_session(
        session_digest=hashlib.sha256(sid.encode()).hexdigest(),
        actor_id="17",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    body = b'{"task_id":2,"user_id":"alice"}'
    response = _request(
        client,
        "POST",
        "/v1/timer/start",
        body=body,
        headers={
            "X-OKR-Token-Version": "1",
            "X-OKR-Session-Id": sid,
            "X-OKR-Session-Actor": "17",
        },
        x_okr_session_id=sid,
        x_okr_session_actor="17",
    )
    assert response.status_code == 401
    assert client.timer_calls == []


def test_revoked_session_and_unavailable_provider_never_reach_handler(
    client, monkeypatch
):
    import backend_app.security as backend_security
    from backend_app.security_state import revoke_session

    sid = "revoked-session-identifier"
    from backend_app.security_state import register_session

    register_session(
        session_digest=hashlib.sha256(sid.encode()).hexdigest(),
        actor_id="17",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    revoke_session(
        session_digest=hashlib.sha256(sid.encode()).hexdigest(),
        now=datetime.now(timezone.utc),
    )
    assert _session_request(client, sid=sid).status_code == 401
    assert client.timer_calls == []

    def unavailable(**_kwargs):
        from backend_app.security_state import SecurityStateUnavailableError

        raise SecurityStateUnavailableError("provider unavailable")

    monkeypatch.setattr(backend_security, "check_session", unavailable, raising=False)
    assert _session_request(client, sid="any-session-identifier").status_code == 503
    assert client.timer_calls == []


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false"),
        ("OKR_BACKEND_ENFORCE_TOKEN", "false"),
    ],
)
def test_internal_register_and_revoke_require_both_service_controls(
    client, monkeypatch, setting, value
):
    body = json.dumps(
        {
            "session_id": "opaque-session",
            "actor_id": 17,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
        },
        separators=(",", ":"),
    ).encode()
    monkeypatch.setenv(setting, value)
    response = _request(
        client, "POST", "/v1/internal/session-registry/register", body=body
    )
    assert response.status_code == 503
