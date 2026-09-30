from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import backend_app.security_state as security_state
from tests._security_state_schema import build_database_store


@pytest.fixture
def database_store(tmp_path):
    store = build_database_store(
        database_url=f"sqlite:///{tmp_path / 'session-registry.db'}",
        cleanup_interval_seconds=3600,
    )
    try:
        yield store
    finally:
        store.dispose()


def test_database_registry_registers_and_checks_digest_keyed_session(database_store):
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    expires_at = now + timedelta(minutes=5)

    database_store.register_session(
        session_digest="a" * 64, actor_id="user-1", expires_at=expires_at
    )

    assert (
        database_store.check_session(
            session_digest="a" * 64, actor_id="user-1", now=now
        )
        == "active"
    )
    assert (
        database_store.check_session(
            session_digest="b" * 64, actor_id="user-1", now=now
        )
        == "unknown"
    )


def test_database_registry_registration_is_idempotent_only_for_same_binding(
    database_store,
):
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    expires_at = now + timedelta(minutes=5)
    values = {
        "session_digest": "c" * 64,
        "actor_id": "user-1",
        "expires_at": expires_at,
    }

    database_store.register_session(**values)
    database_store.register_session(**values)

    with pytest.raises(security_state.SessionRegistrationConflictError):
        database_store.register_session(**{**values, "actor_id": "user-2"})
    with pytest.raises(security_state.SessionRegistrationConflictError):
        database_store.register_session(
            **{**values, "expires_at": expires_at + timedelta(seconds=1)}
        )


def test_database_registry_actor_mismatch_is_not_active(database_store):
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    database_store.register_session(
        session_digest="d" * 64,
        actor_id="user-1",
        expires_at=now + timedelta(minutes=5),
    )

    assert (
        database_store.check_session(
            session_digest="d" * 64, actor_id="user-2", now=now
        )
        == "unknown"
    )


def test_database_registry_revokes_atomically_and_is_idempotent(database_store):
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    database_store.register_session(
        session_digest="e" * 64,
        actor_id="user-1",
        expires_at=now + timedelta(minutes=5),
    )

    assert database_store.revoke_session(session_digest="e" * 64, now=now) == "revoked"
    assert database_store.revoke_session(session_digest="e" * 64, now=now) == "revoked"
    assert (
        database_store.check_session(
            session_digest="e" * 64, actor_id="user-1", now=now
        )
        == "revoked"
    )
    assert database_store.revoke_session(session_digest="f" * 64, now=now) == "unknown"


def test_database_registry_accepts_expiry_second_and_cleans_only_after_it(
    database_store,
):
    expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
    database_store.register_session(
        session_digest="7" * 64,
        actor_id="user-1",
        expires_at=expires_at,
    )

    assert (
        database_store.check_session(
            session_digest="7" * 64, actor_id="user-1", now=expires_at
        )
        == "active"
    )
    assert (
        database_store.check_session(
            session_digest="7" * 64,
            actor_id="user-1",
            now=expires_at + timedelta(microseconds=1),
        )
        == "unknown"
    )
    with database_store._engine.connect() as conn:
        count = conn.execute(
            security_state.text(
                "SELECT COUNT(*) FROM backend_distributed_state WHERE state_key = :key"
            ),
            {"key": database_store._session_state_key("7" * 64)},
        ).scalar_one()
    assert count == 0


def test_database_registry_storage_failure_is_unavailable(tmp_path, monkeypatch):
    store = build_database_store(
        database_url=f"sqlite:///{tmp_path / 'unavailable-session-registry.db'}"
    )
    store._ensure_schema()

    def unavailable_connect():
        from sqlalchemy.exc import OperationalError

        raise OperationalError("connect", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(store._engine, "connect", unavailable_connect)

    with pytest.raises(security_state.SecurityStateUnavailableError):
        store.check_session(
            session_digest="8" * 64,
            actor_id="user-1",
            now=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )


def test_database_generic_state_cannot_read_or_write_session_registry_keys(
    database_store, monkeypatch
):
    reserved_key = database_store._session_state_key("a" * 64)
    database_store.set_app_state("ordinary-state", "before")
    assert database_store.get_app_state("ordinary-state") == "before"

    with pytest.raises(ValueError, match="reserved"):
        database_store.get_app_state(reserved_key)
    with pytest.raises(ValueError, match="reserved"):
        database_store.set_app_state(reserved_key, "overwritten")

    monkeypatch.setattr(security_state, "_get_store", lambda: database_store)
    with pytest.raises(ValueError, match="reserved"):
        security_state.get_app_state(reserved_key)
    with pytest.raises(ValueError, match="reserved"):
        security_state.set_app_state(reserved_key, "overwritten")
    assert security_state.get_app_state("ordinary-state") == "before"


def test_database_cleanup_is_bounded_and_preserves_expiry_equality_and_malformed(
    database_store,
):
    import json

    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(microseconds=1)
    equal_digest = "e" * 64
    malformed_digest = "f" * 64
    expired_digests = [f"{index:064x}" for index in range(1, 106)]

    database_store._ensure_schema()
    with database_store._engine.begin() as conn:
        for index, digest in enumerate(expired_digests):
            record = {
                "actor_id": "user-expired",
                "expires_at": _utc_iso(expired_at),
                "status": "revoked",
                "created_at": _utc_iso(expired_at - timedelta(days=1)),
                "revoked_at": _utc_iso(expired_at),
            }
            conn.execute(
                security_state.text(
                    "INSERT INTO backend_distributed_state "
                    "(state_key, state_value, updated_at) VALUES (:key, :value, :updated)"
                ),
                {
                    "key": database_store._session_state_key(digest),
                    "value": json.dumps(record),
                    "updated": expired_at.replace(tzinfo=None)
                    - timedelta(seconds=1)
                    + timedelta(microseconds=index),
                },
            )
        equal_record = {
            "actor_id": "user-equal",
            "expires_at": _utc_iso(now),
            "status": "active",
            "created_at": _utc_iso(now),
            "revoked_at": None,
        }
        conn.execute(
            security_state.text(
                "INSERT INTO backend_distributed_state "
                "(state_key, state_value, updated_at) VALUES (:key, :value, :updated)"
            ),
            {
                "key": database_store._session_state_key(equal_digest),
                "value": json.dumps(equal_record),
                "updated": now.replace(tzinfo=None),
            },
        )
        conn.execute(
            security_state.text(
                "INSERT INTO backend_distributed_state "
                "(state_key, state_value, updated_at) VALUES (:key, :value, :updated)"
            ),
            {
                "key": database_store._session_state_key(malformed_digest),
                "value": "not-json",
                "updated": now.replace(tzinfo=None),
            },
        )
        conn.execute(
            security_state.text(
                "INSERT INTO backend_distributed_state "
                "(state_key, state_value, updated_at) VALUES (:key, :value, :updated)"
            ),
            {"key": "ordinary-state", "value": "keep", "updated": now},
        )

    database_store._last_cleanup_at = 0
    assert (
        database_store.check_session(
            session_digest=equal_digest, actor_id="user-equal", now=now
        )
        == "active"
    )
    with database_store._engine.connect() as conn:
        remaining_expired = conn.execute(
            security_state.text(
                "SELECT COUNT(*) FROM backend_distributed_state "
                "WHERE state_key LIKE 'session-registry:%' "
                "AND state_key != :equal_key AND state_key != :malformed_key"
            ),
            {
                "equal_key": database_store._session_state_key(equal_digest),
                "malformed_key": database_store._session_state_key(malformed_digest),
            },
        ).scalar_one()
        retained = conn.execute(
            security_state.text(
                "SELECT COUNT(*) FROM backend_distributed_state WHERE state_key IN "
                "(:equal_key, :malformed_key, 'ordinary-state')"
            ),
            {
                "equal_key": database_store._session_state_key(equal_digest),
                "malformed_key": database_store._session_state_key(malformed_digest),
            },
        ).scalar_one()
    assert remaining_expired == 5
    assert retained == 3
    with pytest.raises(security_state.SecurityStateUnavailableError):
        database_store.check_session(
            session_digest=malformed_digest, actor_id="user-malformed", now=now
        )


def test_database_cleanup_does_not_delete_expired_record_with_empty_actor(
    database_store,
):
    import json

    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(seconds=1)
    digest = "0" * 64
    record = {
        "actor_id": "",
        "expires_at": _utc_iso(expires_at),
        "status": "revoked",
        "created_at": _utc_iso(expires_at - timedelta(days=1)),
        "revoked_at": _utc_iso(expires_at),
    }
    database_store._ensure_schema()
    with database_store._engine.begin() as conn:
        conn.execute(
            security_state.text(
                "INSERT INTO backend_distributed_state "
                "(state_key, state_value, updated_at) VALUES (:key, :value, :updated)"
            ),
            {
                "key": database_store._session_state_key(digest),
                "value": json.dumps(record),
                "updated": expires_at.replace(tzinfo=None),
            },
        )
    database_store._last_cleanup_at = 0

    with pytest.raises(security_state.SecurityStateUnavailableError):
        database_store.check_session(session_digest=digest, actor_id="user-1", now=now)
    with database_store._engine.connect() as conn:
        row = conn.execute(
            security_state.text(
                "SELECT state_value FROM backend_distributed_state WHERE state_key = :key"
            ),
            {"key": database_store._session_state_key(digest)},
        ).first()
    assert row is not None


def test_database_cleanup_pages_past_more_than_one_batch_of_retained_records(
    database_store,
):
    import json

    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(seconds=1)
    unexpired_at = now + timedelta(hours=1)
    retained_digests = [f"{index:064x}" for index in range(1, 206)]
    malformed_digest = "0" * 64
    expired_digests = ["e" * 64, "f" * 64]
    registry_rows = []

    for index, digest in enumerate(retained_digests):
        record = {
            "actor_id": "retained-actor",
            "expires_at": _utc_iso(unexpired_at),
            "status": "active",
            "created_at": _utc_iso(now),
            "revoked_at": None,
        }
        registry_rows.append(
            (
                database_store._session_state_key(digest),
                json.dumps(record),
                now.replace(tzinfo=None)
                - timedelta(days=1)
                + timedelta(microseconds=index),
            )
        )
    registry_rows.append(
        (
            database_store._session_state_key(malformed_digest),
            "not-json",
            now.replace(tzinfo=None) - timedelta(days=2),
        )
    )
    for digest in expired_digests:
        record = {
            "actor_id": "expired-actor",
            "expires_at": _utc_iso(expired_at),
            "status": "revoked",
            "created_at": _utc_iso(expired_at - timedelta(days=1)),
            "revoked_at": _utc_iso(expired_at),
        }
        registry_rows.append(
            (
                database_store._session_state_key(digest),
                json.dumps(record),
                now.replace(tzinfo=None),
            )
        )

    database_store._ensure_schema()
    with database_store._engine.begin() as conn:
        for key, value, updated_at in registry_rows:
            conn.execute(
                security_state.text(
                    "INSERT INTO backend_distributed_state "
                    "(state_key, state_value, updated_at) VALUES (:key, :value, :updated)"
                ),
                {"key": key, "value": value, "updated": updated_at},
            )

    expired_keys = [
        database_store._session_state_key(value) for value in expired_digests
    ]
    remaining_counts = []
    for _ in range(3):
        database_store._last_cleanup_at = 0
        database_store._cleanup_if_due(
            now_dt=now.replace(tzinfo=None), now_ts=now.timestamp()
        )
        with database_store._engine.connect() as conn:
            count = conn.execute(
                security_state.text(
                    "SELECT COUNT(*) FROM backend_distributed_state "
                    "WHERE state_key IN (:first, :second)"
                ),
                {"first": expired_keys[0], "second": expired_keys[1]},
            ).scalar_one()
        remaining_counts.append(count)

    assert remaining_counts == [2, 2, 0]
    database_store._last_cleanup_at = 0
    database_store._cleanup_if_due(
        now_dt=now.replace(tzinfo=None), now_ts=now.timestamp()
    )
    assert database_store._session_cleanup_cursor == database_store._session_state_key(
        retained_digests[98]
    )
    assert (
        database_store.check_session(
            session_digest=retained_digests[0],
            actor_id="retained-actor",
            now=now,
        )
        == "active"
    )
    with pytest.raises(security_state.SecurityStateUnavailableError):
        database_store.check_session(
            session_digest=malformed_digest, actor_id="malformed", now=now
        )


def test_postgres_cleanup_pages_past_more_than_one_batch_of_retained_records():
    import json
    import os

    database_url = os.getenv("OKR_TEST_POSTGRES_URL", "").strip()
    if not database_url:
        pytest.skip("OKR_TEST_POSTGRES_URL is not configured")
    store = build_database_store(
        database_url=database_url, cleanup_interval_seconds=3600
    )
    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(seconds=1)
    unexpired_at = now + timedelta(hours=1)
    retained_digests = [f"{index:064x}" for index in range(1000, 1205)]
    malformed_digest = "0" * 64
    expired_digests = ["e" * 64, "f" * 64]
    keys = [store._session_state_key(digest) for digest in retained_digests]
    keys.extend(store._session_state_key(digest) for digest in expired_digests)
    keys.append(store._session_state_key(malformed_digest))

    try:
        store._ensure_schema()
        with store._engine.begin() as conn:
            for index, digest in enumerate(retained_digests):
                record = {
                    "actor_id": "retained-actor",
                    "expires_at": _utc_iso(unexpired_at),
                    "status": "active",
                    "created_at": _utc_iso(now),
                    "revoked_at": None,
                }
                conn.execute(
                    security_state.text(
                        "INSERT INTO backend_distributed_state "
                        "(state_key, state_value, updated_at) "
                        "VALUES (:key, :value, :updated)"
                    ),
                    {
                        "key": store._session_state_key(digest),
                        "value": json.dumps(record),
                        "updated": now.replace(tzinfo=None)
                        - timedelta(days=1)
                        + timedelta(microseconds=index),
                    },
                )
            conn.execute(
                security_state.text(
                    "INSERT INTO backend_distributed_state "
                    "(state_key, state_value, updated_at) "
                    "VALUES (:key, :value, :updated)"
                ),
                {
                    "key": store._session_state_key(malformed_digest),
                    "value": "not-json",
                    "updated": now.replace(tzinfo=None) - timedelta(days=2),
                },
            )
            for digest in expired_digests:
                record = {
                    "actor_id": "expired-actor",
                    "expires_at": _utc_iso(expired_at),
                    "status": "revoked",
                    "created_at": _utc_iso(expired_at - timedelta(days=1)),
                    "revoked_at": _utc_iso(expired_at),
                }
                conn.execute(
                    security_state.text(
                        "INSERT INTO backend_distributed_state "
                        "(state_key, state_value, updated_at) "
                        "VALUES (:key, :value, :updated)"
                    ),
                    {
                        "key": store._session_state_key(digest),
                        "value": json.dumps(record),
                        "updated": now.replace(tzinfo=None),
                    },
                )

        remaining_counts = []
        expired_keys = [store._session_state_key(digest) for digest in expired_digests]
        for _ in range(3):
            store._last_cleanup_at = 0
            store._cleanup_if_due(
                now_dt=now.replace(tzinfo=None), now_ts=now.timestamp()
            )
            with store._engine.connect() as conn:
                remaining_counts.append(
                    conn.execute(
                        security_state.text(
                            "SELECT COUNT(*) FROM backend_distributed_state "
                            "WHERE state_key IN (:first, :second)"
                        ),
                        {"first": expired_keys[0], "second": expired_keys[1]},
                    ).scalar_one()
                )
        assert remaining_counts == [2, 2, 0]

        store._last_cleanup_at = 0
        store._cleanup_if_due(now_dt=now.replace(tzinfo=None), now_ts=now.timestamp())
        assert store._session_cleanup_cursor == store._session_state_key(
            retained_digests[98]
        )
        assert (
            store.check_session(
                session_digest=retained_digests[0],
                actor_id="retained-actor",
                now=now,
            )
            == "active"
        )
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.check_session(
                session_digest=malformed_digest, actor_id="malformed", now=now
            )
    finally:
        with store._engine.begin() as conn:
            conn.execute(
                security_state.text(
                    "DELETE FROM backend_distributed_state WHERE state_key = ANY(:keys)"
                ),
                {"keys": keys},
            )
        store.dispose()


def test_postgres_registry_cleanup_is_bounded_and_preserves_expiry_equality():
    import hashlib
    import json
    import os
    import uuid

    database_url = os.getenv("OKR_TEST_POSTGRES_URL", "").strip()
    if not database_url:
        pytest.skip("OKR_TEST_POSTGRES_URL is not configured")
    store = build_database_store(
        database_url=database_url, cleanup_interval_seconds=3600
    )
    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(microseconds=1)
    expired_digests = [f"{index:064x}" for index in range(1, 106)]
    equal_digest = hashlib.sha256(f"t23-equal-{uuid.uuid4()}".encode()).hexdigest()
    malformed_digest = hashlib.sha256(
        f"t23-malformed-{uuid.uuid4()}".encode()
    ).hexdigest()
    keys = [store._session_state_key(value) for value in expired_digests]
    keys.extend(
        [
            store._session_state_key(equal_digest),
            store._session_state_key(malformed_digest),
        ]
    )
    try:
        store._ensure_schema()
        with store._engine.begin() as conn:
            for index, digest in enumerate(expired_digests):
                record = {
                    "actor_id": "expired-actor",
                    "expires_at": _utc_iso(expired_at),
                    "status": "revoked",
                    "created_at": _utc_iso(expired_at - timedelta(days=1)),
                    "revoked_at": _utc_iso(expired_at),
                }
                conn.execute(
                    security_state.text(
                        "INSERT INTO backend_distributed_state "
                        "(state_key, state_value, updated_at) "
                        "VALUES (:key, :value, :updated)"
                    ),
                    {
                        "key": store._session_state_key(digest),
                        "value": json.dumps(record),
                        "updated": expired_at.replace(tzinfo=None)
                        - timedelta(seconds=1)
                        + timedelta(microseconds=index),
                    },
                )
            equal_record = {
                "actor_id": "equal-actor",
                "expires_at": _utc_iso(now),
                "status": "active",
                "created_at": _utc_iso(now),
                "revoked_at": None,
            }
            conn.execute(
                security_state.text(
                    "INSERT INTO backend_distributed_state "
                    "(state_key, state_value, updated_at) "
                    "VALUES (:key, :value, :updated)"
                ),
                {
                    "key": store._session_state_key(equal_digest),
                    "value": json.dumps(equal_record),
                    "updated": now.replace(tzinfo=None),
                },
            )
            conn.execute(
                security_state.text(
                    "INSERT INTO backend_distributed_state "
                    "(state_key, state_value, updated_at) "
                    "VALUES (:key, :value, :updated)"
                ),
                {
                    "key": store._session_state_key(malformed_digest),
                    "value": "not-json",
                    "updated": now.replace(tzinfo=None),
                },
            )
        store._last_cleanup_at = 0
        assert (
            store.check_session(
                session_digest=equal_digest, actor_id="equal-actor", now=now
            )
            == "active"
        )
        with store._engine.connect() as conn:
            remaining_expired = conn.execute(
                security_state.text(
                    "SELECT COUNT(*) FROM backend_distributed_state "
                    "WHERE state_key LIKE 'session-registry:%' "
                    "AND state_key NOT IN (:equal_key, :malformed_key)"
                ),
                {
                    "equal_key": store._session_state_key(equal_digest),
                    "malformed_key": store._session_state_key(malformed_digest),
                },
            ).scalar_one()
            equal_count = conn.execute(
                security_state.text(
                    "SELECT COUNT(*) FROM backend_distributed_state WHERE state_key = :key"
                ),
                {"key": store._session_state_key(equal_digest)},
            ).scalar_one()
            malformed_count = conn.execute(
                security_state.text(
                    "SELECT COUNT(*) FROM backend_distributed_state WHERE state_key = :key"
                ),
                {"key": store._session_state_key(malformed_digest)},
            ).scalar_one()
        assert remaining_expired == 5
        assert equal_count == 1
        assert malformed_count == 1
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.check_session(
                session_digest=malformed_digest,
                actor_id="malformed-actor",
                now=now,
            )
    finally:
        with store._engine.begin() as conn:
            conn.execute(
                security_state.text(
                    "DELETE FROM backend_distributed_state WHERE state_key = ANY(:keys)"
                ),
                {"keys": keys},
            )
        store.dispose()


@pytest.mark.parametrize("backend", ["database", "redis"])
def test_configured_durable_registry_does_not_fall_back_to_memory(monkeypatch, backend):
    import types

    monkeypatch.setattr(
        security_state,
        "get_backend_settings",
        lambda: types.SimpleNamespace(security_state_backend=backend),
    )
    monkeypatch.setattr(
        security_state, "_get_store", lambda: security_state._memory_store
    )

    with pytest.raises(security_state.SecurityStateUnavailableError):
        security_state.register_session(
            session_digest="9" * 64,
            actor_id="user-1",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )


def test_redis_registry_atomic_contract_when_redis_configured(monkeypatch):
    import json
    import os
    import uuid

    redis_url = os.getenv("OKR_TEST_REDIS_URL", "").strip()
    if not redis_url:
        pytest.skip("OKR_TEST_REDIS_URL is not configured")
    prefix = f"t23-test-{uuid.uuid4().hex}"
    store = security_state.RedisSecurityStateStore(
        redis_url=redis_url, key_prefix=prefix
    )
    digest = "a" * 64
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    try:
        store.register_session(
            session_digest=digest, actor_id="user-1", expires_at=expires_at
        )
        reserved_key = f"session-registry:{digest}"
        with pytest.raises(ValueError, match="reserved"):
            store.get_app_state(reserved_key)
        with pytest.raises(ValueError, match="reserved"):
            store.set_app_state(reserved_key, "overwritten")
        store.register_session(
            session_digest=digest, actor_id="user-1", expires_at=expires_at
        )
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="user-1",
                now=expires_at,
            )
            == "active"
        )
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="user-2",
                now=expires_at,
            )
            == "unknown"
        )
        with pytest.raises(security_state.SessionRegistrationConflictError):
            store.register_session(
                session_digest=digest,
                actor_id="user-2",
                expires_at=expires_at,
            )
        with pytest.raises(security_state.SessionRegistrationConflictError):
            store.register_session(
                session_digest=digest,
                actor_id="user-1",
                expires_at=expires_at + timedelta(seconds=1),
            )
        assert store.revoke_session(session_digest=digest, now=expires_at) == "revoked"
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="user-1",
                now=expires_at,
            )
            == "revoked"
        )
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="user-1",
                now=expires_at + timedelta(microseconds=1),
            )
            == "unknown"
        )
        malformed_digest = "b" * 64
        store._client.set(store._session_key(malformed_digest), "{")
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.check_session(
                session_digest=malformed_digest,
                actor_id="user-1",
                now=expires_at,
            )
        malformed_expiry_digest = "c" * 64
        store._client.set(
            store._session_key(malformed_expiry_digest),
            '{"actor_id":"user-1","expires_at":"invalid","status":"active"}',
        )
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.check_session(
                session_digest=malformed_expiry_digest,
                actor_id="user-1",
                now=expires_at,
            )
        malformed_actor_digest = "e" * 64
        store._client.set(
            store._session_key(malformed_actor_digest),
            json.dumps(
                {
                    "actor_id": "",
                    "expires_at": security_state._session_epoch_microseconds(
                        expires_at
                    ),
                    "status": "active",
                }
            ),
        )
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.check_session(
                session_digest=malformed_actor_digest,
                actor_id="user-1",
                now=expires_at,
            )
        out_of_range_digest = "d" * 64
        store._client.set(
            store._session_key(out_of_range_digest),
            '{"actor_id":"user-1","expires_at":"99999999999999999999",'
            '"status":"active"}',
        )
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.check_session(
                session_digest=out_of_range_digest,
                actor_id="user-1",
                now=expires_at,
            )

        monkeypatch.setattr(
            store._client,
            "eval",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("redis unavailable")
            ),
        )
        with pytest.raises(security_state.SecurityStateUnavailableError):
            store.revoke_session(session_digest="c" * 64, now=expires_at)
    finally:
        store._client.delete(
            store._session_key(digest),
            store._session_key("b" * 64),
            store._session_key("c" * 64),
            store._session_key("d" * 64),
            store._session_key("e" * 64),
        )
        store.dispose()


def test_redis_session_key_expires_after_last_acceptable_microsecond():
    import os
    import time
    import uuid

    redis_url = os.getenv("OKR_TEST_REDIS_URL", "").strip()
    if not redis_url:
        pytest.skip("OKR_TEST_REDIS_URL is not configured")
    store = security_state.RedisSecurityStateStore(
        redis_url=redis_url, key_prefix=f"t23-expiry-{uuid.uuid4().hex}"
    )
    digest = "9" * 64
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(milliseconds=500)
    key = store._session_key(digest)
    try:
        store.register_session(
            session_digest=digest, actor_id="expiry-actor", expires_at=expires_at
        )
        assert store._client.pttl(key) > 0
        assert store.revoke_session(session_digest=digest, now=now) == "revoked"
        assert store._client.pttl(key) > 0
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="expiry-actor",
                now=expires_at,
            )
            == "revoked"
        )
        time.sleep(0.75)
        assert store._client.get(key) is None
    finally:
        store._client.delete(key)
        store.dispose()


def test_database_registry_uses_atomic_shared_operations_when_postgres_configured():
    import os

    database_url = os.getenv("OKR_TEST_POSTGRES_URL", "").strip()
    if not database_url:
        pytest.skip("OKR_TEST_POSTGRES_URL is not configured")
    store = build_database_store(
        database_url=database_url,
        cleanup_interval_seconds=3600,
    )
    digest = (
        __import__("hashlib")
        .sha256(f"t23-postgres-{__import__('uuid').uuid4()}".encode())
        .hexdigest()
    )
    now = datetime.now(timezone.utc)
    try:
        store.register_session(
            session_digest=digest,
            actor_id="t23-postgres-actor",
            expires_at=now + timedelta(minutes=5),
        )
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="t23-postgres-actor",
                now=now,
            )
            == "active"
        )
        assert store.revoke_session(session_digest=digest, now=now) == "revoked"
        assert (
            store.check_session(
                session_digest=digest,
                actor_id="t23-postgres-actor",
                now=now,
            )
            == "revoked"
        )
    finally:
        with store._engine.begin() as conn:
            conn.execute(
                security_state.text(
                    "DELETE FROM backend_distributed_state WHERE state_key = :key"
                ),
                {"key": store._session_state_key(digest)},
            )
        store.dispose()


def test_database_registry_concurrent_operations_use_shared_row_locking():
    import os
    import uuid
    from concurrent.futures import ThreadPoolExecutor

    database_url = os.getenv("OKR_TEST_POSTGRES_URL", "").strip()
    if not database_url:
        pytest.skip("OKR_TEST_POSTGRES_URL is not configured")
    stores = [
        build_database_store(database_url=database_url, cleanup_interval_seconds=3600)
        for _ in range(2)
    ]
    digest = (
        __import__("hashlib")
        .sha256(f"t23-concurrent-{uuid.uuid4()}".encode())
        .hexdigest()
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)
    try:
        for store in stores:
            store._ensure_schema()

        def register(index):
            return stores[index % 2].register_session(
                session_digest=digest,
                actor_id="same-actor",
                expires_at=expires_at,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(register, range(8)))
        assert (
            stores[1].check_session(
                session_digest=digest, actor_id="same-actor", now=now
            )
            == "active"
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    stores[0].revoke_session, session_digest=digest, now=now
                ),
                executor.submit(
                    stores[1].check_session,
                    session_digest=digest,
                    actor_id="same-actor",
                    now=now,
                ),
            ]
            observed = [future.result() for future in futures]
        assert observed[0] == "revoked"
        assert observed[1] in {"active", "revoked"}
        assert (
            stores[1].check_session(
                session_digest=digest, actor_id="same-actor", now=now
            )
            == "revoked"
        )
    finally:
        for store in stores:
            with store._engine.begin() as conn:
                conn.execute(
                    security_state.text(
                        "DELETE FROM backend_distributed_state WHERE state_key = :key"
                    ),
                    {"key": store._session_state_key(digest)},
                )
            store.dispose()


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")
