"""Regression coverage for alignment edge serialization in the read API."""

from datetime import timedelta

from fastapi.testclient import TestClient
import pytest

from conftest import utc_now_naive


def test_alignment_context_serializes_persisted_edge(read_alignment_client):
    client, parent_id, child_id = read_alignment_client

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alignment_reader"},
        json={"kind": "alignments.context", "params": {"objective_id": child_id}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["edges"] == [
        {
            "id": 1,
            "parent_id": parent_id,
            "child_id": child_id,
            "alignment_type": "SUPPORTS",
        }
    ]


@pytest.fixture()
def read_alignment_client(monkeypatch, isolated_db):
    import backend_app.main as backend_main
    from src.crud import create_cycle, create_goal, create_objective, create_user
    from src.database import get_session_context
    from src.models import AlignmentEdge

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_DATA_ACCESS_MODE", "database")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)

    create_user("alignment_reader", "reader-pass")
    cycle = create_cycle(
        "Alignment read cycle",
        start_date=utc_now_naive(),
        end_date=utc_now_naive() + timedelta(days=90),
    )
    goal = create_goal(
        "alignment_reader",
        title="Alignment read goal",
        cycle_id=cycle.id,
        actor_username="alignment_reader",
    )
    parent = create_objective(
        goal.id, "Parent objective", actor_username="alignment_reader"
    )
    child = create_objective(
        goal.id, "Child objective", actor_username="alignment_reader"
    )
    with get_session_context() as session:
        session.add(
            AlignmentEdge(
                parent_id=parent.id,
                child_id=child.id,
                created_by="alignment_reader",
            )
        )
        session.commit()

    with TestClient(backend_main.app) as client:
        yield client, parent.id, child.id
