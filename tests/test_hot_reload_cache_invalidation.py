from __future__ import annotations

import sys
import types


def test_model_refresh_clears_streamlit_cache_once_on_identity_change(
    monkeypatch,
) -> None:
    import src.database as database

    clear_calls = {"count": 0}

    def _clear_cache() -> None:
        clear_calls["count"] += 1

    fake_streamlit = types.SimpleNamespace(
        cache_data=types.SimpleNamespace(clear=_clear_cache)
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    # Force a perceived model-identity change.
    database._last_models_identity = -1
    database._refresh_loaded_model_references_if_needed()
    assert clear_calls["count"] == 1


def test_model_refresh_does_not_clear_cache_on_first_identity_set(monkeypatch) -> None:
    import src.database as database

    clear_calls = {"count": 0}

    def _clear_cache() -> None:
        clear_calls["count"] += 1

    fake_streamlit = types.SimpleNamespace(
        cache_data=types.SimpleNamespace(clear=_clear_cache)
    )
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    database._last_models_identity = None
    database._refresh_loaded_model_references_if_needed()
    assert clear_calls["count"] == 0

    # Second call with same identity should not clear again.
    database._refresh_loaded_model_references_if_needed()
    assert clear_calls["count"] == 0
