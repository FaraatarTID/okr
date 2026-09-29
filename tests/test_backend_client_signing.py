import pytest


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_backend_client_adds_signing_headers_when_secret_configured(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "super-secret-signing-key")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_KEY_ID", "rotated-key-2026")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", "service-token")

    captured = {}

    def _fake_request_with_retry(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = dict(kwargs.get("headers") or {})
        captured["body_bytes"] = kwargs.get("body_bytes")
        return _FakeResponse({"id": 1, "node_type": "GOAL", "title": "x"})

    monkeypatch.setattr(backend_client, "request_with_retry", _fake_request_with_retry)

    backend_client.create_goal(
        user_id="alice",
        title="Goal X",
        description="Y",
        actor_username="alice",
    )

    headers = captured["headers"]
    assert headers.get("X-OKR-Service-Token") == "service-token"
    assert headers.get("X-OKR-Key-Id") == "rotated-key-2026"
    assert "X-OKR-Signature" in headers
    assert "X-OKR-Timestamp" in headers
    assert "X-OKR-Nonce" in headers
    assert len(str(headers["X-OKR-Signature"])) >= 32


def test_backend_client_omits_key_id_when_unconfigured(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "super-secret-signing-key")
    monkeypatch.delenv("OKR_BACKEND_SIGNING_KEY_ID", raising=False)

    headers = backend_client._headers(
        "alice", method="GET", url="http://backend.local/v1/example", body_bytes=b""
    )

    assert "X-OKR-Signature" in headers
    assert "X-OKR-Key-Id" not in headers


def test_backend_client_omits_key_id_without_signing_secret(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.delenv("OKR_BACKEND_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("OKR_BACKEND_SIGNING_KEY_ID", "rotated-key-2026")

    headers = backend_client._headers(
        "alice", method="GET", url="http://backend.local/v1/example", body_bytes=b""
    )

    assert "X-OKR-Signature" not in headers
    assert "X-OKR-Key-Id" not in headers


def test_backend_client_drops_caller_key_id_without_signing_secret(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.delenv("OKR_BACKEND_SIGNING_SECRET", raising=False)
    monkeypatch.setenv("OKR_BACKEND_SIGNING_KEY_ID", "configured-key")

    headers = backend_client._headers(
        "alice",
        method="POST",
        url="http://backend.local/v1/example",
        body_bytes=b"{}",
        extra_headers={
            "x-oKr-KeY-iD": "caller-key",
            "X-OKR-Idempotency-Key": "operation-1",
        },
    )

    assert all(key.lower() != "x-okr-key-id" for key in headers)
    assert headers["X-OKR-Idempotency-Key"] == "operation-1"
    assert "X-OKR-Signature" not in headers


def test_backend_client_signature_binds_optional_session_assertions(monkeypatch):
    import hashlib
    import hmac

    import src.services.backend_client as backend_client
    from src.utils.crypto_utils import body_digest_hex, canonical_signing_payload

    secret = "session-bound-signing-key"
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", secret)
    headers = backend_client._headers(
        "alice",
        method="POST",
        url="http://backend.local/v1/example",
        body_bytes=b"{}",
        extra_headers={
            "X-OKR-Session-Id": "opaque-session",
            "X-OKR-Session-Actor": "17",
        },
    )
    payload = canonical_signing_payload(
        method="POST",
        path="/v1/example",
        timestamp=headers["X-OKR-Timestamp"],
        nonce=headers["X-OKR-Nonce"],
        body_digest=body_digest_hex(b"{}"),
        session_id="opaque-session",
        session_actor="17",
    )
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert headers["X-OKR-Signature"] == expected

    actor_only = canonical_signing_payload(
        method="POST",
        path="/v1/example",
        timestamp=headers["X-OKR-Timestamp"],
        nonce=headers["X-OKR-Nonce"],
        body_digest=body_digest_hex(b"{}"),
        session_actor="17",
    )
    assert actor_only != payload


def test_internal_cache_client_call_is_explicitly_actorless_and_signed(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", "cache-signing-secret")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_KEY_ID", "cache-key")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", "cache-service-token")
    captured = {}

    def fake_request_with_retry(method, url, **kwargs):
        captured.update(method=method, url=url, headers=dict(kwargs["headers"]))
        return _FakeResponse({"status": "updated"})

    monkeypatch.setattr(backend_client, "request_with_retry", fake_request_with_retry)
    result = backend_client.request_internal_cache_invalidation(
        method="POST", timestamp="1729"
    )

    assert result == {"status": "updated"}
    assert captured["url"] == ("http://backend.local/v1/internal/cache-invalidation")
    headers = captured["headers"]
    assert headers["X-OKR-Service-Token"] == "cache-service-token"
    assert headers["X-OKR-Key-Id"] == "cache-key"
    assert "X-OKR-Signature" in headers
    assert not any(
        name.lower()
        in {
            "x-okr-actor",
            "x-okr-token-version",
            "x-okr-session-id",
            "x-okr-session-actor",
        }
        for name in headers
    )


def test_internal_cache_client_call_rejects_arbitrary_methods(monkeypatch):
    import src.services.backend_client as backend_client

    with pytest.raises(ValueError, match="GET or POST"):
        backend_client.request_internal_cache_invalidation(method="DELETE")
