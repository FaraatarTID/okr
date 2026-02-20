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
