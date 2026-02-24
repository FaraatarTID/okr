from __future__ import annotations

import sys
from types import SimpleNamespace


class _FakeCacheData:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1


def _install_fake_streamlit(monkeypatch):
    fake_st = SimpleNamespace(cache_data=_FakeCacheData())
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    return fake_st


def test_clear_cache_safe_clears_local_cache_and_broadcasts(monkeypatch):
    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    fake_st = _install_fake_streamlit(monkeypatch)
    calls = {"broadcast": 0}

    monkeypatch.setattr(
        distributed_state_service,
        "broadcast_cache_invalidation",
        lambda: calls.__setitem__("broadcast", calls["broadcast"] + 1) or True,
    )

    cache_utils.clear_cache_safe()

    assert fake_st.cache_data.clear_calls == 1
    assert calls["broadcast"] == 1


def test_check_distributed_cache_staleness_clears_on_any_signal_change(monkeypatch):
    import src.services.distributed_state_service as distributed_state_service
    import src.utils.cache_utils as cache_utils

    fake_st = _install_fake_streamlit(monkeypatch)
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

    assert fake_st.cache_data.clear_calls == 2
