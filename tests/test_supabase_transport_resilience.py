"""Tests for Supabase transport concurrency limit, circuit breaker, and shutdown."""

from __future__ import annotations

import threading
import time

import httpx
import pytest

from src.services import supabase_api_mode_transport as transport


@pytest.fixture(autouse=True)
def _reset_transport_state(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    transport.reset_circuit_breaker()
    yield
    transport.reset_circuit_breaker()
    transport.shutdown_close_transport()


def _force_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Replace the cached client with one backed by a mock transport."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(transport, "_HTTP_CLIENT", client)
    monkeypatch.setattr(
        transport, "_HTTP_CLIENT_CONFIG", ("https://example.supabase.co", "")
    )


class TestConcurrencyLimit:
    def test_semaphore_limits_in_flight_requests(self, monkeypatch):
        active = {"n": 0}
        max_active = {"n": 0}
        lock = threading.Lock()

        def handler(request: httpx.Request) -> httpx.Response:
            with lock:
                active["n"] += 1
                max_active["n"] = max(max_active["n"], active["n"])
            time.sleep(0.05)
            with lock:
                active["n"] -= 1
            return httpx.Response(200, json=[])

        _force_client(monkeypatch, handler)
        # Force a tiny semaphore by rebuilding it (cached per-process).
        monkeypatch.setattr(
            transport, "_CONCURRENCY_SEMAPHORE", threading.BoundedSemaphore(2)
        )

        threads = [
            threading.Thread(target=transport._request_json, args=("/rest/v1/t",))
            for _ in range(6)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert max_active["n"] <= 2

    def test_semaphore_released_after_failure(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        _force_client(monkeypatch, handler)
        transport.reset_circuit_breaker()

        for _ in range(3):
            with pytest.raises(transport.SupabaseTransportError):
                transport._request_json("/rest/v1/t")

        # Semaphore must be fully available again (acquire all permits).
        sem = transport._get_concurrency_semaphore()
        for _ in range(sem._initial_value if hasattr(sem, "_initial_value") else 4):
            assert sem.acquire(blocking=False)
            sem.release()


class TestCircuitBreaker:
    def test_opens_after_consecutive_failures(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

        _force_client(monkeypatch, handler)
        monkeypatch.setattr(transport, "_breaker_threshold", lambda: 3)
        monkeypatch.setattr(transport, "_breaker_cooldown_s", lambda: 60.0)

        for i in range(3):
            with pytest.raises(transport.SupabaseTransportError) as exc_info:
                transport._request_json("/rest/v1/t")
            assert exc_info.value.kind != "circuit_open" or i >= 2

        # Breaker now open: next call fails fast without hitting transport.
        with pytest.raises(transport.CircuitOpenError):
            transport._request_json("/rest/v1/t")

    def test_half_open_probe_after_cooldown(self, monkeypatch):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=[])

        _force_client(monkeypatch, handler)
        monkeypatch.setattr(transport, "_breaker_threshold", lambda: 1)
        monkeypatch.setattr(transport, "_breaker_cooldown_s", lambda: 0.05)

        # Trip the breaker.
        monkeypatch.setattr(
            transport,
            "_HTTP_CLIENT",
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda r: (_ for _ in ()).throw(httpx.ConnectError("x", request=r))
                )
            ),
        )
        with pytest.raises(transport.SupabaseTransportError):
            transport._request_json("/rest/v1/t")

        # Wait out cooldown, restore healthy client, probe succeeds and closes.
        time.sleep(0.06)
        _force_client(monkeypatch, handler)
        status, payload = transport._request_json("/rest/v1/t")
        assert status == 200
        # Subsequent requests also pass (breaker closed).
        status, _ = transport._request_json("/rest/v1/t")
        assert status == 200

    def test_success_resets_failure_count(self, monkeypatch):

        def failing(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("x", request=request)

        def ok(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        _force_client(monkeypatch, failing)
        monkeypatch.setattr(transport, "_breaker_threshold", lambda: 3)

        with pytest.raises(transport.SupabaseTransportError):
            transport._request_json("/rest/v1/t")
        with pytest.raises(transport.SupabaseTransportError):
            transport._request_json("/rest/v1/t")

        # A success resets the counter so breaker never opens.
        _force_client(monkeypatch, ok)
        status, _ = transport._request_json("/rest/v1/t")
        assert status == 200

        _force_client(monkeypatch, failing)
        with pytest.raises(transport.SupabaseTransportError):
            transport._request_json("/rest/v1/t")
        with pytest.raises(transport.SupabaseTransportError):
            transport._request_json("/rest/v1/t")
        # Only 2 consecutive failures since last success -> still closed.
        _force_client(monkeypatch, ok)
        status, _ = transport._request_json("/rest/v1/t")
        assert status == 200


class TestShutdownLifecycle:
    def test_shutdown_closes_client(self, monkeypatch):
        closed = {"flag": False}
        client = httpx.Client()

        original_close = client.close

        def tracking_close() -> None:
            closed["flag"] = True
            original_close()

        monkeypatch.setattr(client, "close", tracking_close)
        monkeypatch.setattr(transport, "_HTTP_CLIENT", client)
        monkeypatch.setattr(
            transport, "_HTTP_CLIENT_CONFIG", ("https://example.supabase.co", "")
        )

        transport.shutdown_close_transport()
        assert closed["flag"] is True
        assert transport._HTTP_CLIENT is None
        assert transport._HTTP_CLIENT_CONFIG is None

    def test_shutdown_is_idempotent(self):
        transport.shutdown_close_transport()
        transport.shutdown_close_transport()  # must not raise

    def test_lifespan_calls_shutdown_on_exit(self):
        import asyncio

        from backend_app.main_bootstrap_helpers import make_main_lifespan

        called = {"shutdown": False}

        import src.services.supabase_api_mode_transport as t

        original = t.shutdown_close_transport

        def spy() -> None:
            called["shutdown"] = True
            original()

        t.shutdown_close_transport = spy  # type: ignore[assignment]
        try:
            lifespan = make_main_lifespan(
                is_supabase_api_mode_enabled=lambda: False,
                ensure_supabase_api_ready=lambda: None,
                init_database=lambda: None,
                ensure_admin_exists=lambda: None,
            )
            async def _run() -> None:
                cm = lifespan(None)
                await cm.__aenter__()
                await cm.__aexit__(None, None, None)

            asyncio.run(_run())
            assert called["shutdown"] is True
        finally:
            t.shutdown_close_transport = original  # type: ignore[assignment]
