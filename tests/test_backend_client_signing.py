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
    assert "X-OKR-Signature" in headers
    assert "X-OKR-Timestamp" in headers
    assert "X-OKR-Nonce" in headers
    assert len(str(headers["X-OKR-Signature"])) >= 32


def test_local_backend_fallback_flag_defaults_off(monkeypatch):
    import src.services.backend_client as backend_client

    monkeypatch.delenv("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", raising=False)
    assert backend_client.allow_local_backend_fallback() is False

    monkeypatch.setenv("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", "true")
    assert backend_client.allow_local_backend_fallback() is True
