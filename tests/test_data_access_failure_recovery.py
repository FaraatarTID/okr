from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

import backend_app.data_access_mode as dam


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


def test_concurrent_request_contexts_do_not_share_data_access_state(monkeypatch):
    import src.database as database

    thread_probe = threading.local()

    def _is_primary_available() -> bool:
        return bool(getattr(thread_probe, "primary_available", True))

    monkeypatch.setattr(database, "is_direct_db_available", _is_primary_available)
    monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
    monkeypatch.setattr(dam, "_https_credentials_configured", lambda: True)

    a_ready = threading.Event()
    b_ready = threading.Event()

    def _run_request(actor: str, primary_available: bool):
        thread_probe.primary_available = primary_available
        with dam.data_access_context(actor=actor):
            if actor == "alice":
                a_ready.set()
                assert b_ready.wait(2)
            else:
                b_ready.set()
                assert a_ready.wait(2)
            mode = dam.resolve_read_mode()
            context = dam.current_data_access_context()
            assert context is not None
            return {
                "actor": context.actor,
                "mode": mode,
                "resolver_state": context.resolver_state,
            }

    with ThreadPoolExecutor(max_workers=2) as executor:
        alice_future = executor.submit(_run_request, "alice", True)
        bob_future = executor.submit(_run_request, "bob", False)
        alice = alice_future.result()
        bob = bob_future.result()

    assert alice["actor"] == "alice"
    assert bob["actor"] == "bob"
    assert alice["mode"] == "database"
    assert bob["mode"] == "supabase_api"
    assert alice["resolver_state"] == "primary_available"
    assert bob["resolver_state"] == "fallback_available"


def test_read_mode_recovery_after_tcp_probe_reset(monkeypatch):
    import src.database as database

    state = {"primary_up": False, "reset_called": 0}

    def _is_primary_available() -> bool:
        return bool(state["primary_up"])

    def _reset_probe_cache() -> None:
        state["reset_called"] += 1

    monkeypatch.setattr(database, "is_direct_db_available", _is_primary_available)
    monkeypatch.setattr(database, "reset_direct_db_status", _reset_probe_cache)
    monkeypatch.setattr(dam, "_env_explicit_api_mode", lambda: False)
    monkeypatch.setattr(dam, "_https_credentials_configured", lambda: True)

    with dam.data_access_context(actor="alice"):
        assert dam.resolve_read_mode() == "supabase_api"
        context = dam.current_data_access_context()
        assert context is not None
        assert context.resolver_state == "fallback_available"
        assert context.fallback_reason == "direct_database_unavailable"

    state["primary_up"] = True
    dam.notify_tcp_db_failure()
    assert state["reset_called"] == 1

    with dam.data_access_context(actor="alice"):
        assert dam.resolve_read_mode() == "database"
        context = dam.current_data_access_context()
        assert context is not None
        assert context.resolver_state == "primary_available"


def test_mutation_recovery_path_does_not_fallback_to_supabase_on_db_failure(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    import backend_app.main_mutation_handlers as main_mutation_handlers

    calls = {"db": 0, "supabase": 0}

    monkeypatch.setattr(
        main_mutation_handlers,
        "_resolve_actor",
        lambda *_args, **_kwargs: "alice",
    )
    monkeypatch.setattr(
        main_mutation_handlers,
        "_atomic_idempotent_check",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        main_mutation_handlers,
        "_payload_to_jsonable",
        lambda payload: payload,
    )
    monkeypatch.setattr(
        main_mutation_handlers,
        "_complete_idempotent_response",
        lambda **_kwargs: None,
    )

    def _create_goal_db_failure(*_args, **_kwargs):
        calls["db"] += 1
        raise RuntimeError("direct-db write failed")

    def _create_goal_supabase(*_args, **_kwargs):
        calls["supabase"] += 1
        raise AssertionError("read-mode fallback should not hit supabase mutation path")

    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: False)
    monkeypatch.setattr(backend_main, "create_goal", _create_goal_db_failure)
    monkeypatch.setattr(backend_main, "create_goal_via_supabase_api", _create_goal_supabase)

    response = client.post(
        "/v1/nodes/goal",
        headers={"X-OKR-Actor": "alice"},
        json={
            "user_id": "alice",
            "title": "Recovery gate",
            "description": "fault injection",
            "strategy_tags": [],
        },
    )

    assert response.status_code == 500
    assert calls["db"] == 1
    assert calls["supabase"] == 0
