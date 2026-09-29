"""Contracts of the blind-except handlers reviewed in backend_app/worker.py and security_state.py.

Each handler swallows on purpose. These tests pin what the swallow must do, so narrowing or
widening one changes a test, not only a `noqa` comment.
"""

from __future__ import annotations

import sys
import types

import pytest

import backend_app.worker as worker
from backend_app import security_state

# --- worker ---------------------------------------------------------------------------------


def test_job_thread_re_raises_base_exceptions_in_the_caller(monkeypatch):
    """`except BaseException` in the job thread exists so SystemExit is not lost with the thread."""

    def boom(_kind, _payload):
        raise SystemExit(7)

    monkeypatch.setattr(worker, "run_job", boom)
    with pytest.raises(SystemExit) as caught:
        worker._run_job_with_lifecycle("any.kind", {})
    assert caught.value.code == 7


def test_job_thread_returns_the_result_when_nothing_is_raised(monkeypatch):
    monkeypatch.setattr(worker, "run_job", lambda _k, _p: {"ok": 1})
    assert worker._run_job_with_lifecycle("any.kind", {}) == {"ok": 1}


def _capture_exception_logs(monkeypatch) -> list[str]:
    logs: list[str] = []
    monkeypatch.setattr(
        worker.logger, "exception", lambda payload: logs.append(str(payload))
    )
    return logs


def test_claim_failure_is_logged_and_the_iteration_reports_no_work(monkeypatch):
    logs = _capture_exception_logs(monkeypatch)

    def broken(_worker_id):
        raise RuntimeError("db down")

    monkeypatch.setattr(worker, "claim_next_pending_job", broken)
    assert worker.process_next_job(worker_id="w1") is False
    assert any("worker_claim_failed" in line for line in logs)


@pytest.mark.parametrize("terminal", [True, False])
def test_failed_status_write_is_logged_and_does_not_raise(monkeypatch, terminal):
    logs = _capture_exception_logs(monkeypatch)

    def broken(*_args, **_kwargs):
        raise RuntimeError("status write failed")

    monkeypatch.setattr(worker, "mark_job_failed", broken)
    monkeypatch.setattr(worker, "mark_job_failed_terminal", broken)
    worker._safe_mark_job_failed(job_id="j1", error_text="x", terminal=terminal)
    assert any("worker_job_failure_state_error" in line for line in logs)


def test_failed_status_write_uses_the_terminal_writer_only_when_terminal(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        worker, "mark_job_failed", lambda *_a, **_k: calls.append("retry")
    )
    monkeypatch.setattr(
        worker, "mark_job_failed_terminal", lambda *_a, **_k: calls.append("terminal")
    )
    worker._safe_mark_job_failed(job_id="j", error_text="x", terminal=True)
    worker._safe_mark_job_failed(job_id="j", error_text="x", terminal=False)
    assert calls == ["terminal", "retry"]


# --- security state: JSON fallbacks ---------------------------------------------------------

SCOPE, ACTOR, KEY = "scope", "actor", "key"


def _reserve(store) -> None:
    assert store.reserve_idempotency_key(
        scope=SCOPE, actor=ACTOR, key=KEY, payload_hash="h", ttl_seconds=60
    )


def test_memory_store_keeps_a_non_json_response_string(monkeypatch):
    store = security_state.InMemorySecurityStateStore()
    _reserve(store)
    store.store_idempotent_response(
        scope=SCOPE, actor=ACTOR, key=KEY, response_json="not json"
    )
    record = store.load_idempotent_response(scope=SCOPE, actor=ACTOR, key=KEY)
    assert record is not None
    assert record["response"] == "not json"


def test_memory_store_decodes_a_json_response():
    store = security_state.InMemorySecurityStateStore()
    _reserve(store)
    store.store_idempotent_response(
        scope=SCOPE, actor=ACTOR, key=KEY, response_json='{"a": 1}'
    )
    record = store.load_idempotent_response(scope=SCOPE, actor=ACTOR, key=KEY)
    assert record is not None and record["response"] == {"a": 1}


def test_database_store_reports_no_response_for_corrupt_json(tmp_path):
    store = security_state.DatabaseSecurityStateStore(
        database_url=f"sqlite:///{tmp_path / 'idem.db'}"
    )
    try:
        _reserve(store)
        store.store_idempotent_response(
            scope=SCOPE, actor=ACTOR, key=KEY, response_json="{broken"
        )
        record = store.load_idempotent_response(scope=SCOPE, actor=ACTOR, key=KEY)
        assert record is not None
        assert record["payload_hash"] == "h"
        assert record["response"] is None
    finally:
        store.dispose()


def test_database_store_decodes_a_json_response(tmp_path):
    store = security_state.DatabaseSecurityStateStore(
        database_url=f"sqlite:///{tmp_path / 'idem.db'}"
    )
    try:
        _reserve(store)
        store.store_idempotent_response(
            scope=SCOPE, actor=ACTOR, key=KEY, response_json='{"a": 1}'
        )
        record = store.load_idempotent_response(scope=SCOPE, actor=ACTOR, key=KEY)
        assert record is not None and record["response"] == {"a": 1}
    finally:
        store.dispose()


# --- security state: Redis handlers (fail closed, never raise) ------------------------------


class _BrokenClient:
    def ping(self):
        return True

    def get(self, *_a, **_k):
        raise RuntimeError("redis unavailable")

    def ttl(self, *_a, **_k):
        raise RuntimeError("redis unavailable")

    def set(self, *_a, **_k):
        raise RuntimeError("redis unavailable")

    def close(self):
        raise RuntimeError("close failed")


def _redis_store(monkeypatch, client):
    monkeypatch.setitem(
        sys.modules,
        "redis",
        types.SimpleNamespace(
            Redis=types.SimpleNamespace(from_url=lambda *_a, **_k: client)
        ),
    )
    return security_state.RedisSecurityStateStore(redis_url="redis://fake:6379/0")


def test_redis_load_returns_none_when_redis_fails(monkeypatch):
    store = _redis_store(monkeypatch, _BrokenClient())
    assert store.load_idempotent_response(scope=SCOPE, actor=ACTOR, key=KEY) is None


def test_redis_store_does_not_raise_when_redis_fails(monkeypatch):
    class Half(_BrokenClient):
        def get(self, *_a, **_k):
            return b'{"ph": "h"}'

    store = _redis_store(monkeypatch, Half())
    store.store_idempotent_response(
        scope=SCOPE, actor=ACTOR, key=KEY, response_json='{"a": 1}'
    )


def test_a_failed_idempotent_load_makes_the_caller_answer_409(monkeypatch):
    """The reason the Redis swallow is safe: the caller never replays a wrong response."""
    from fastapi import HTTPException

    from backend_app import main_helpers

    monkeypatch.setattr(main_helpers, "reserve_idempotency_key", lambda **_k: False)
    monkeypatch.setattr(main_helpers, "load_idempotent_response", lambda **_k: None)
    with pytest.raises(HTTPException) as caught:
        main_helpers.atomic_idempotent_check(
            scope=SCOPE, actor=ACTOR, idempotency_key="k1", payload={"a": 1}
        )
    assert caught.value.status_code == 409


def test_dispose_swallows_client_close_errors(monkeypatch):
    store = _redis_store(monkeypatch, _BrokenClient())
    store.dispose()
