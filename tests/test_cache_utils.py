from __future__ import annotations

import sys
from types import SimpleNamespace


def test_clear_cache_safe_broadcasts(monkeypatch):
    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    calls = {"broadcast": 0}

    monkeypatch.setattr(
        distributed_state_service,
        "broadcast_cache_invalidation",
        lambda: calls.__setitem__("broadcast", calls["broadcast"] + 1) or True,
    )

    cache_utils.clear_cache_safe()

    assert calls["broadcast"] == 1


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
