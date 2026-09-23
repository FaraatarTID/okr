"""Regression coverage for task Work History read serialization."""

from datetime import timedelta

from fastapi.testclient import TestClient
import pytest

from conftest import utc_now_naive


def test_work_logs_by_task_returns_rows_in_descending_start_order(work_log_read_client):
    client, task_id = work_log_read_client

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "work_history_reader"},
        json={"kind": "work_logs.by_task", "params": {"task_id": task_id}},
    )

    assert response.status_code == 200, response.text
    rows = response.json()["work_logs"]
    assert [row["summary"] for row in rows] == ["newer work", "older work"]
    assert [row["id"] for row in rows] == [2, 1]


@pytest.fixture()
def work_log_read_client(monkeypatch, isolated_db):
    import backend_app.main as backend_main
    from src.crud import (
        create_cycle,
        create_goal,
        create_key_result,
        create_objective,
        create_task,
        create_user,
    )
    from src.database import get_session_context
    from src.models import WorkLog

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "database")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)

    create_user("work_history_reader", "reader-pass")
    now = utc_now_naive()
    cycle = create_cycle(
        "Work history cycle",
        start_date=now,
        end_date=now + timedelta(days=90),
    )
    goal = create_goal(
        "work_history_reader",
        title="Work history goal",
        cycle_id=cycle.id,
        actor_username="work_history_reader",
    )
    objective = create_objective(
        goal.id, "Work history objective", actor_username="work_history_reader"
    )
    key_result = create_key_result(
        objective.id, "Work history KR", actor_username="work_history_reader"
    )
    task = create_task(
        key_result.id, "Work history task", actor_username="work_history_reader"
    )
    with get_session_context() as session:
        session.add_all(
            [
                WorkLog(
                    task_id=task.id,
                    start_time=now - timedelta(minutes=30),
                    end_time=now - timedelta(minutes=10),
                    duration_minutes=20,
                    summary="older work",
                ),
                WorkLog(
                    task_id=task.id,
                    start_time=now - timedelta(minutes=20),
                    end_time=now - timedelta(minutes=5),
                    duration_minutes=15,
                    summary="newer work",
                ),
            ]
        )
        session.commit()

    with TestClient(backend_main.app) as client:
        yield client, task.id
