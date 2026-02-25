import pytest


def test_leadership_read_fails_closed_when_local_fallback_disabled(monkeypatch):
    import src.services.backend_client as backend_client
    import src.ui.components as components

    components._cached_get_leadership_metrics.clear()
    monkeypatch.setenv("OKR_ALLOW_LOCAL_READ_FALLBACK", "false")
    monkeypatch.setattr(components, "_backend_read_proxy_enabled", lambda: True)
    monkeypatch.setattr(
        backend_client,
        "fetch_leadership_metrics",
        lambda **kwargs: {"error": "backend unavailable", "status_code": 503},
    )

    import src.crud as crud

    monkeypatch.setattr(
        crud,
        "get_leadership_metrics",
        lambda *args, **kwargs: pytest.fail("Local fallback should not execute."),
    )

    with pytest.raises(RuntimeError, match="local fallback is disabled"):
        components._cached_get_leadership_metrics(
            ("alice",),
            1,
            actor_username="alice",
        )


def test_atlas_snapshot_read_fails_closed_when_local_fallback_disabled(monkeypatch):
    import src.services.backend_client as backend_client
    import src.ui.components as components

    components._cached_get_atlas_scope_snapshot.clear()
    monkeypatch.setenv("OKR_ALLOW_LOCAL_READ_FALLBACK", "false")
    monkeypatch.setattr(components, "_backend_read_proxy_enabled", lambda: True)
    monkeypatch.setattr(
        backend_client,
        "fetch_atlas_scope_snapshot",
        lambda **kwargs: {"error": "backend unavailable", "status_code": 503},
    )

    def _unexpected_local_session():
        raise AssertionError("Local DB fallback should not execute.")

    monkeypatch.setattr(components, "get_session_context", _unexpected_local_session)

    with pytest.raises(RuntimeError, match="local fallback is disabled"):
        components._cached_get_atlas_scope_snapshot(
            1,
            (1,),
            include_analysis=False,
            actor_username="alice",
        )
