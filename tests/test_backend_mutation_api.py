from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
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


def test_submit_job_endpoint_returns_429_when_quota_exceeded(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _raise_quota(*args, **kwargs):
        raise HTTPException(status_code=429, detail="quota exceeded")

    monkeypatch.setattr(backend_main, "enforce_job_submit_limits", _raise_quota)

    response = client.post(
        "/v1/jobs",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "ai.generate_json", "payload": {"prompt": "hello"}},
    )

    assert response.status_code == 429
    assert "quota" in str(response.json().get("detail", "")).lower()


def test_submit_job_endpoint_forwards_idempotency_key(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    monkeypatch.setattr(
        backend_main,
        "enforce_job_submit_limits",
        lambda **kwargs: None,
    )

    def _fake_enqueue_job(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="job-1")

    monkeypatch.setattr(backend_main, "enqueue_job", _fake_enqueue_job)
    monkeypatch.setattr(
        backend_main,
        "serialize_job",
        lambda job: {
            "id": "job-1",
            "kind": "ai.generate_json",
            "status": "pending",
            "actor_username": "alice",
            "team_id": 1,
            "attempts": 0,
            "max_attempts": 2,
            "cancel_requested": False,
            "idempotency_key": captured.get("idempotency_key"),
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error_text": None,
        },
    )

    response = client.post(
        "/v1/jobs",
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Idempotency-Key": "abc-123",
        },
        json={"kind": "ai.generate_json", "payload": {"prompt": "hello"}},
    )

    assert response.status_code == 202
    assert captured.get("idempotency_key") == "abc-123"
