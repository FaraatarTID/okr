import pytest


def test_create_goal_uses_backend_mutation_proxy(monkeypatch):
    import src.crud as crud
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")

    monkeypatch.setattr(
        backend_client,
        "create_goal",
        lambda **kwargs: {
            "id": 901,
            "node_type": "GOAL",
            "title": "Proxy Goal",
            "description": "Created via backend",
            "progress": 0,
            "owner_id": 1,
        },
    )

    goal = crud.create_goal(
        user_id="alice",
        title="Proxy Goal",
        description="Created via backend",
        actor_username="alice",
    )
    assert int(goal.id) == 901
    assert goal.title == "Proxy Goal"


def test_update_task_backend_permission_error_bubbles(monkeypatch):
    import src.crud as crud
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")

    monkeypatch.setattr(
        backend_client,
        "update_node",
        lambda **kwargs: {"error": "Insufficient permissions.", "status_code": 403},
    )

    with pytest.raises(PermissionError):
        crud.update_task(12, title="x", actor_username="alice")


def test_create_goal_backend_transient_error_fails_closed_by_default(monkeypatch):
    import src.crud as crud
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")
    monkeypatch.delenv("OKR_ALLOW_LOCAL_MUTATION_FALLBACK", raising=False)
    monkeypatch.delenv("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", raising=False)

    monkeypatch.setattr(
        backend_client,
        "create_goal",
        lambda **kwargs: {"error": "connection refused", "status_code": 0},
    )

    with pytest.raises(ValueError, match="fallback is disabled"):
        crud.create_goal(
            user_id="alice",
            title="Proxy Goal",
            description="Created via backend",
            actor_username="alice",
        )


def test_create_cycle_uses_backend_mutation_proxy(monkeypatch):
    import src.crud as crud
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")

    monkeypatch.setattr(
        backend_client,
        "create_cycle",
        lambda **kwargs: {
            "id": 77,
            "title": kwargs.get("title"),
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-03-31T00:00:00",
            "is_active": True,
        },
    )

    cycle = crud.create_cycle(
        title="Q1 2026",
        start_date="2026-01-01T00:00:00",
        end_date="2026-03-31T00:00:00",
        actor_username="admin",
    )
    assert int(cycle.id) == 77
    assert cycle.title == "Q1 2026"


def test_create_check_in_backend_permission_error_bubbles(monkeypatch):
    import src.crud as crud
    import src.services.backend_client as backend_client
    from src.models import VariationType

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")

    monkeypatch.setattr(
        backend_client,
        "create_check_in",
        lambda **kwargs: {"error": "Insufficient permissions.", "status_code": 403},
    )

    with pytest.raises(PermissionError):
        crud.create_check_in(
            kr_id=12,
            value=55.0,
            confidence=8,
            comment="x",
            actor_username="bob",
            variation_type=VariationType.COMMON_CAUSE,
        )


def test_reset_user_password_uses_backend_mutation_proxy(monkeypatch):
    import src.crud as crud
    import src.services.backend_client as backend_client

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_BACKEND_PROXY_MUTATIONS", "true")

    monkeypatch.setattr(
        backend_client,
        "reset_user_password",
        lambda **kwargs: {"user_id": int(kwargs.get("user_id")), "reset": True},
    )

    ok = crud.reset_user_password(
        user_id=5,
        new_password="new-secret",
        actor_username="admin",
        require_change=True,
    )
    assert ok is True
