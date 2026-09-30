from __future__ import annotations


def test_clear_cache_safe_broadcasts(monkeypatch):
    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    calls = {"broadcast": 0}

    monkeypatch.setattr(
        distributed_state_service, "is_broadcast_configured", lambda: True
    )
    monkeypatch.setattr(
        distributed_state_service,
        "broadcast_cache_invalidation",
        lambda: calls.__setitem__("broadcast", calls["broadcast"] + 1) or True,
    )

    cache_utils.clear_cache_safe()

    assert calls["broadcast"] == 1


def test_clear_cache_safe_skips_quietly_without_backend_url(monkeypatch, caplog):
    """The shipped compose file gives the API and worker no OKR_BACKEND_API_URL.

    Every write used to log two warnings there. With nothing to broadcast to, that is
    a configuration fact, so nothing is sent and nothing is logged above DEBUG.
    """
    import logging

    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    sent = []
    monkeypatch.setattr(
        distributed_state_service, "is_broadcast_configured", lambda: False
    )
    monkeypatch.setattr(
        distributed_state_service,
        "broadcast_cache_invalidation",
        lambda: sent.append(1) or True,
    )

    with caplog.at_level(logging.WARNING):
        cache_utils.clear_cache_safe()

    assert sent == []
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_clear_cache_safe_still_warns_when_configured_broadcast_fails(
    monkeypatch, caplog
):
    """A real failure with a URL configured must stay visible."""
    import logging

    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    monkeypatch.setattr(
        distributed_state_service, "is_broadcast_configured", lambda: True
    )
    monkeypatch.setattr(
        distributed_state_service, "broadcast_cache_invalidation", lambda: False
    )

    with caplog.at_level(logging.WARNING):
        cache_utils.clear_cache_safe()

    assert any(
        "Failed to broadcast distributed cache invalidation" in r.getMessage()
        for r in caplog.records
    )


def test_is_broadcast_configured_follows_the_backend_url(monkeypatch):
    import src.services.distributed_state_service as service

    monkeypatch.setattr(service, "_base_url", lambda: "")
    assert service.is_broadcast_configured() is False
    monkeypatch.setattr(service, "_base_url", lambda: "http://backend-api:8100")
    assert service.is_broadcast_configured() is True


def test_check_distributed_cache_staleness_detects_signal_change(monkeypatch):
    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    signals = iter([10, 7, 7])
    monkeypatch.setattr(cache_utils, "_LAST_SEEN_INVALIDATION_TS", 0)
    monkeypatch.setattr(
        distributed_state_service,
        "get_last_invalidation_timestamp",
        lambda: next(signals),
    )

    cache_utils.check_distributed_cache_staleness()
    cache_utils.check_distributed_cache_staleness()
    cache_utils.check_distributed_cache_staleness()

    assert cache_utils._LAST_SEEN_INVALIDATION_TS == 7
