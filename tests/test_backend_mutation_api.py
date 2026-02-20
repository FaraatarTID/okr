from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


def test_create_goal_endpoint_normalizes_tag_list(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_create_goal(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=101,
            title=str(kwargs.get("title") or ""),
            description=str(kwargs.get("description") or ""),
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_goal", _fake_create_goal)

    response = client.post(
        "/v1/nodes/goal",
        headers={"X-OKR-Actor": "alice"},
        json={
            "user_id": "alice",
            "title": "Grow Revenue",
            "description": "Q2 focus",
            "strategy_tags": ["North Star", "Retention"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["node_type"] == "GOAL"
    assert int(payload["id"]) == 101
    assert captured["strategy_tags"] == '["North Star", "Retention"]'


def test_update_task_endpoint_coerces_enum_and_datetime(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_update_task(task_id, actor_username=None, **updates):
        captured["task_id"] = task_id
        captured["actor_username"] = actor_username
        captured["updates"] = updates
        return SimpleNamespace(
            id=task_id,
            title="Task A",
            description="",
            progress=55,
            owner_id=7,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, "update_task", _fake_update_task)

    response = client.patch(
        "/v1/nodes/task/77",
        headers={"X-OKR-Actor": "alice"},
        json={
            "updates": {
                "status": "done",
                "start_date": "2026-01-15T10:30:00Z",
                "deadline": 1760000000000,
            }
        },
    )

    assert response.status_code == 200
    assert int(captured["task_id"]) == 77
    assert captured["actor_username"] == "alice"
    assert str(captured["updates"]["status"].value) == "done"
    assert isinstance(captured["updates"]["start_date"], datetime)
    assert isinstance(captured["updates"]["deadline"], datetime)
