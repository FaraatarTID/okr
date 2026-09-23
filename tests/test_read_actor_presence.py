"""F2: protected read kinds require an actor on the public HTTP path."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from conftest import utc_now_naive


READ_CASES = (
    ("node.get", "node", lambda ids: {"node_id": ids["task"], "node_type": "TASK"}),
    ("node.detect_type", "node_type", lambda ids: {"node_id": ids["task"]}),
    ("work_logs.by_task", "work_logs", lambda ids: {"task_id": ids["task"]}),
    ("experiments.for_kr", "experiments", lambda ids: {"key_result_id": ids["kr"]}),
    (
        "experiments.active_for_kr",
        "experiments",
        lambda ids: {"key_result_id": ids["kr"]},
    ),
    ("alignments.context", "parents", lambda ids: {"objective_id": ids["objective"]}),
    (
        "mindmap.root",
        "node",
        lambda ids: {"node_id": ids["task"], "node_type": "TASK"},
    ),
)


@pytest.fixture()
def read_client(monkeypatch, isolated_db):
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
    from src.models import Experiment, ExperimentStatus

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "database")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)

    reader = create_user("f2_reader", "reader-pass")
    cycle = create_cycle(
        "F2 read cycle",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    goal = create_goal(
        "f2_reader", title="F2 goal", cycle_id=cycle.id, actor_username="f2_reader"
    )
    objective = create_objective(goal.id, "F2 objective", actor_username="f2_reader")
    kr = create_key_result(objective.id, "F2 KR", actor_username="f2_reader")
    create_task(kr.id, "F2 first task", actor_username="f2_reader")
    # Each node table has its own sequence. Choose a task id that cannot be
    # mistaken for the goal/objective/KR id by detect_type's probe order.
    task = create_task(kr.id, "F2 target task", actor_username="f2_reader")
    with get_session_context() as session:
        session.add(
            Experiment(
                key_result_id=kr.id,
                cycle_id=cycle.id,
                created_by="f2_reader",
                hypothesis="F2 hypothesis",
                change_description="F2 change",
                status=ExperimentStatus.RUNNING,
            )
        )
        session.commit()

    ids = {
        "user": reader.id,
        "goal": goal.id,
        "objective": objective.id,
        "kr": kr.id,
        "task": task.id,
    }
    with TestClient(backend_main.app) as client:
        yield client, ids


@pytest.mark.parametrize("kind,section,params_for", READ_CASES)
def test_actorless_read_is_rejected_before_scope_or_data_access(
    read_client, monkeypatch, kind, section, params_for
):
    import backend_app.main as backend_main

    client, ids = read_client
    reached_scope = []
    original_resolver = backend_main._resolve_scope_for_actor

    def tracked_scope(actor, *args, **kwargs):
        reached_scope.append(actor)
        return original_resolver(actor, *args, **kwargs)

    monkeypatch.setattr(backend_main, "_resolve_scope_for_actor", tracked_scope)
    response = client.post(
        "/v1/read/query",
        json={"kind": kind, "params": params_for(ids)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Actor username is required."
    assert reached_scope == []


@pytest.mark.parametrize("kind,section,params_for", READ_CASES)
def test_payload_actor_cannot_override_verified_header_actor(
    read_client, monkeypatch, kind, section, params_for
):
    import backend_app.main as backend_main

    client, ids = read_client
    reached_scope = []
    original_resolver = backend_main._resolve_scope_for_actor

    def tracked_scope(actor, *args, **kwargs):
        reached_scope.append(actor)
        return original_resolver(actor, *args, **kwargs)

    monkeypatch.setattr(backend_main, "_resolve_scope_for_actor", tracked_scope)
    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "f2_reader"},
        json={
            "kind": kind,
            "params": params_for(ids),
            "actor_username": "forged_payload_actor",
        },
    )

    assert response.status_code == 403
    assert "Actor mismatch" in response.json()["detail"]
    assert reached_scope == []


@pytest.mark.parametrize("kind,section,params_for", READ_CASES)
def test_authorized_actor_reaches_real_read_dispatch(
    read_client, monkeypatch, kind, section, params_for
):
    client, ids = read_client
    if kind == "node.get":
        import backend_app.main as backend_main
        from src.models import Task

        def serialize_authorized_task(node_type, node):
            # Serialization runs after the real scope resolver and get_node
            # authorization. Existing detached relationship loading in the
            # full serializer is a separate payload defect.
            assert node_type == "TASK"
            assert isinstance(node, Task)
            assert node.id == ids["task"]
            return {
                "id": node.id,
                "key_result": {"objective": {"goal": {"owner_id": ids["user"]}}},
            }

        monkeypatch.setattr(
            backend_main, "_serialize_node_for_type", serialize_authorized_task
        )
    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "f2_reader"},
        json={"kind": kind, "params": params_for(ids)},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert section in payload
    if kind in {"node.get", "mindmap.root"}:
        assert payload["node"]["id"] == ids["task"]
    elif kind == "node.detect_type":
        assert payload["node_type"] == "TASK"
    elif kind in {"experiments.for_kr", "experiments.active_for_kr"}:
        assert len(payload["experiments"]) == 1
