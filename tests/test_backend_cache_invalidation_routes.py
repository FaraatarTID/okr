from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient


SECRET = "cache-invalidation-test-signing-secret"
TOKEN = "cache-invalidation-test-service-token"
KEY_ID = "cache-test-key"
PATH = "/v1/internal/cache-invalidation"


def _request(client, method, path, *, body=b"", nonce=None, headers=None):
    timestamp = str(int(time.time()))
    request_nonce = nonce or f"nonce-{time.time_ns()}"
    signature = hmac.new(
        SECRET.encode(),
        "\n".join(
            [method.upper(), path, timestamp, request_nonce, hashlib.sha256(body).hexdigest()]
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    request_headers = {
        "X-OKR-Service-Token": TOKEN,
        "X-OKR-Key-Id": KEY_ID,
        "X-OKR-Timestamp": timestamp,
        "X-OKR-Nonce": request_nonce,
        "X-OKR-Signature": signature,
        "Content-Type": "application/json",
    }
    request_headers.update(headers or {})
    return client.request(method, path, content=body, headers=request_headers)


@pytest.fixture
def client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "true")
    monkeypatch.setenv("OKR_BACKEND_SIGNING_SECRET", SECRET)
    monkeypatch.setenv("OKR_BACKEND_SIGNING_KEY_ID", KEY_ID)
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    return TestClient(backend_main.app)


def test_internal_cache_invalidation_is_actorless_and_fixed_purpose(client):
    read = _request(client, "GET", PATH)
    assert read.status_code == 200
    assert read.json() == {"key": "okr:cache:invalidation_ts", "value": None}

    body = json.dumps({"timestamp": "1729"}, separators=(",", ":")).encode()
    write = _request(client, "POST", PATH, body=body)
    assert write.status_code == 200
    assert write.json() == {
        "key": "okr:cache:invalidation_ts",
        "value": "1729",
        "status": "updated",
    }
    assert _request(client, "GET", PATH).json()["value"] == "1729"
    assert client.get(f"{PATH}/arbitrary-key").status_code == 404


def test_internal_cache_invalidation_requires_both_controls_and_advertised_key_id(
    client,
):
    missing_token = _request(
        client, "GET", PATH, headers={"X-OKR-Service-Token": ""}
    )
    assert missing_token.status_code == 401

    invalid_token = _request(
        client, "GET", PATH, headers={"X-OKR-Service-Token": "invalid"}
    )
    assert invalid_token.status_code == 401

    invalid_signature = _request(
        client, "GET", PATH, headers={"X-OKR-Signature": "invalid"}
    )
    assert invalid_signature.status_code == 401

    missing_signature = _request(client, "GET", PATH, headers={"X-OKR-Signature": ""})
    assert missing_signature.status_code == 401

    missing_key_id = _request(client, "GET", PATH, headers={"X-OKR-Key-Id": ""})
    assert missing_key_id.status_code == 401

    wrong_key_id = _request(client, "GET", PATH, headers={"X-OKR-Key-Id": "old"})
    assert wrong_key_id.status_code == 401

    repeated_nonce = "one-use-cache-nonce"
    assert _request(client, "GET", PATH, nonce=repeated_nonce).status_code == 200
    assert _request(client, "GET", PATH, nonce=repeated_nonce).status_code == 401


@pytest.mark.parametrize("timestamp", ["0", "-1", "1.0", "١٢٣"])
def test_cache_invalidation_rejects_invalid_timestamp(client, timestamp):
    body = json.dumps({"timestamp": timestamp}, separators=(",", ":")).encode()
    response = _request(client, "POST", PATH, body=body)
    assert response.status_code == 422


def test_generic_state_route_remains_actor_and_session_bound(client):
    response = _request(client, "GET", "/v1/state/ordinary-key")
    assert response.status_code == 401
    assert response.json()["detail"] == "Actor-bound route requires a signed actor."


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false"),
        ("OKR_BACKEND_ENFORCE_TOKEN", "false"),
    ],
)
def test_internal_cache_route_fails_closed_when_a_service_control_is_disabled(
    client, monkeypatch, setting, value
):
    monkeypatch.setenv(setting, value)
    response = _request(client, "GET", PATH)
    assert response.status_code == 503


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("backend", ["database", "redis"])
def test_cache_invalidation_reports_configured_shared_state_failure(
    client, monkeypatch, tmp_path, method, backend
):
    import backend_app.security_state as security_state

    def unavailable(*_args, **_kwargs):
        raise security_state.SecurityStateUnavailableError("provider unavailable")

    if backend == "database":
        store = security_state.DatabaseSecurityStateStore(
            database_url=f"sqlite:///{tmp_path / 'shared-state.db'}"
        )
        store._ensure_schema()
        monkeypatch.setattr(store, "get_app_state", lambda _key: "legacy-value")
        monkeypatch.setattr(store, "get_app_state_strict", unavailable, raising=False)
        monkeypatch.setattr(store, "set_app_state", unavailable)
    else:
        class UnavailableRedis:
            def get(self, _key):
                raise OSError("redis unavailable")

            def set(self, _key, _value):
                raise OSError("redis unavailable")

        store = object.__new__(security_state.RedisSecurityStateStore)
        store._key_prefix = "test-cache"
        store._client = UnavailableRedis()
        monkeypatch.setattr(store, "register_nonce_once", lambda **_kwargs: True)
        monkeypatch.setattr(store, "check_rate_limit", lambda **_kwargs: True)

    memory_fallbacks = []

    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", backend)
    monkeypatch.setenv(
        "OKR_DATABASE_URL", f"sqlite:///{tmp_path / 'shared-state.db'}"
    )
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_REDIS_URL", "redis://unused")
    monkeypatch.setattr(security_state, "_get_store", lambda: store)
    monkeypatch.setattr(
        security_state,
        "_fallback_to_memory_store",
        lambda: memory_fallbacks.append(True) or security_state._memory_store,
    )
    body = b'{"timestamp":"1729"}' if method == "POST" else b""
    response = _request(client, method, PATH, body=body)
    assert response.status_code == 503
    assert memory_fallbacks == []


def test_database_app_state_read_failure_preserves_generic_none_and_strict_error(
    tmp_path, monkeypatch
):
    import backend_app.security_state as security_state
    from sqlalchemy.exc import OperationalError

    store = security_state.DatabaseSecurityStateStore(
        database_url=f"sqlite:///{tmp_path / 'db-read-failure.db'}"
    )
    store._ensure_schema()

    def unavailable_connect():
        raise OperationalError("connect", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(store._engine, "connect", unavailable_connect)
    assert store.get_app_state("cache-test") is None
    with pytest.raises(security_state.SecurityStateUnavailableError):
        store.get_app_state_strict("cache-test")


def test_redis_app_state_read_failure_preserves_generic_none_and_strict_error():
    import backend_app.security_state as security_state

    class UnavailableRedis:
        def get(self, _key):
            raise OSError("redis unavailable")

    store = object.__new__(security_state.RedisSecurityStateStore)
    store._key_prefix = "test"
    store._client = UnavailableRedis()
    assert store.get_app_state("cache-test") is None
    with pytest.raises(security_state.SecurityStateUnavailableError):
        store.get_app_state_strict("cache-test")


def test_database_app_state_write_failure_is_typed_unavailable(tmp_path, monkeypatch):
    import backend_app.security_state as security_state
    from sqlalchemy.exc import OperationalError

    store = security_state.DatabaseSecurityStateStore(
        database_url=f"sqlite:///{tmp_path / 'db-write-failure.db'}"
    )
    store._ensure_schema()

    def unavailable_begin():
        raise OperationalError("begin", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(store._engine, "begin", unavailable_begin)
    with pytest.raises(security_state.SecurityStateUnavailableError):
        store.set_app_state("cache-test", "1729")


def test_redis_app_state_write_failure_is_typed_unavailable():
    import backend_app.security_state as security_state

    class UnavailableRedis:
        def set(self, _key, _value):
            raise OSError("redis unavailable")

    store = object.__new__(security_state.RedisSecurityStateStore)
    store._key_prefix = "test"
    store._client = UnavailableRedis()
    with pytest.raises(security_state.SecurityStateUnavailableError):
        store.set_app_state("cache-test", "1729")


@pytest.mark.parametrize("backend", ["database", "redis"])
def test_strict_shared_state_rejects_dev_factory_memory_fallback(
    client, monkeypatch, backend
):
    import backend_app.security_state as security_state

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", backend)
    monkeypatch.setenv("OKR_DATABASE_URL", "")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_REDIS_URL", "")
    assert isinstance(
        security_state._get_store(), security_state.InMemorySecurityStateStore
    )
    with pytest.raises(security_state.SecurityStateUnavailableError):
        security_state.get_shared_app_state("cache-test")


@pytest.mark.parametrize("backend", ["database", "redis"])
def test_generic_production_read_outage_does_not_fallback_to_memory(
    monkeypatch, tmp_path, backend
):
    import backend_app.security_state as security_state
    from sqlalchemy.exc import OperationalError

    if backend == "database":
        store = security_state.DatabaseSecurityStateStore(
            database_url=f"sqlite:///{tmp_path / 'generic-read.db'}"
        )
        store._ensure_schema()

        def unavailable_read():
            raise OperationalError("connect", {}, RuntimeError("database unavailable"))

        monkeypatch.setattr(store._engine, "connect", unavailable_read)
    else:
        class UnavailableRedis:
            def get(self, _key):
                raise OSError("redis unavailable")

        store = object.__new__(security_state.RedisSecurityStateStore)
        store._key_prefix = "test-generic"
        store._client = UnavailableRedis()

    fallbacks = []
    monkeypatch.setenv("OKR_ENV", "production")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", backend)
    monkeypatch.setattr(security_state, "_get_store", lambda: store)
    monkeypatch.setattr(
        security_state,
        "_fallback_to_memory_store",
        lambda: fallbacks.append(True) or security_state._memory_store,
    )

    assert security_state.get_app_state("cache-test") is None
    assert fallbacks == []
