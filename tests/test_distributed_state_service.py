from __future__ import annotations


def test_broadcast_cache_invalidation_uses_monotonic_ns_signal(monkeypatch):
    import src.services.distributed_state_service as service

    sent: list[tuple[str, int, str]] = []
    ticks = iter([1_000, 1_000, 999])

    monkeypatch.setattr(service, "_LAST_BROADCAST_TS", 0)
    monkeypatch.setattr(service.time, "time_ns", lambda: next(ticks))
    monkeypatch.setattr(
        service,
        "set_distributed_state",
        lambda key, value, actor_username="system": sent.append(
            (str(key), int(value), str(actor_username))
        )
        or True,
    )

    assert service.broadcast_cache_invalidation(actor_username="alice") is True
    assert service.broadcast_cache_invalidation(actor_username="alice") is True
    assert service.broadcast_cache_invalidation(actor_username="alice") is True

    assert [entry[0] for entry in sent] == [service.KEY_CACHE_INVALIDATION_TS] * 3
    assert [entry[2] for entry in sent] == ["alice", "alice", "alice"]
    values = [entry[1] for entry in sent]
    assert values == [1_000, 1_001, 1_002]


def test_get_last_invalidation_timestamp_parses_int_or_returns_zero(monkeypatch):
    import src.services.distributed_state_service as service

    monkeypatch.setattr(service, "get_distributed_state", lambda _key: "1729")
    assert service.get_last_invalidation_timestamp() == 1729

    monkeypatch.setattr(service, "get_distributed_state", lambda _key: "not-a-number")
    assert service.get_last_invalidation_timestamp() == 0

    monkeypatch.setattr(service, "get_distributed_state", lambda _key: None)
    assert service.get_last_invalidation_timestamp() == 0
