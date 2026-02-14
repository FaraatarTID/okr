from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest
from sqlmodel import SQLModel, select


ROOT_DIR = Path(__file__).resolve().parent
APP_DIR = ROOT_DIR / "streamlit_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    import src.database as database

    db_path = tmp_path / "okr_sync_test.db"
    db_url = f"sqlite:///{db_path}"
    engine = database._create_engine(db_url)

    monkeypatch.setattr(database, "DATABASE_URL", db_url, raising=False)
    monkeypatch.setattr(database, "_engine", engine, raising=False)

    SQLModel.metadata.create_all(engine)
    try:
        yield
    finally:
        engine.dispose()


def test_sync_cleanup_uses_owner_id_for_goal_selection(isolated_db):
    from src.crud import create_user
    from src.database import get_session_context
    from src.models import Goal
    from utils.sync import sync_data_to_db

    alice = create_user("alice", "alice-pass")
    bob = create_user("bob", "bob-pass")

    with get_session_context() as session:
        alice_goal = Goal(
            owner_id=alice.id,
            title="Alice stale goal",
            external_id="goal_alice_stale",
            created_at=_utc_now_naive(),
        )
        bob_goal = Goal(
            owner_id=bob.id,
            title="Bob goal",
            external_id="goal_bob_keep",
            created_at=_utc_now_naive(),
        )
        session.add(alice_goal)
        session.add(bob_goal)

    sync_data_to_db("alice", {"nodes": {}, "rootIds": []})

    with get_session_context() as session:
        remaining = session.exec(select(Goal)).all()
        external_ids = {g.external_id for g in remaining}
        assert "goal_alice_stale" not in external_ids
        assert "goal_bob_keep" in external_ids


def test_sync_new_goal_sets_owner_id_for_normalized_ownership(isolated_db):
    from src.crud import create_user
    from src.database import get_session_context
    from src.models import Goal
    from utils.sync import sync_data_to_db

    alice = create_user("alice", "alice-pass")

    payload = {
        "nodes": {
            "goal_ext_1": {
                "id": "goal_ext_1",
                "type": "GOAL",
                "title": "Synced Goal",
                "description": "From JSON sync",
                "children": [],
            }
        },
        "rootIds": ["goal_ext_1"],
    }

    sync_data_to_db("alice", payload)

    with get_session_context() as session:
        goal = session.exec(select(Goal).where(Goal.external_id == "goal_ext_1")).first()
        assert goal is not None
        assert goal.owner_id == alice.id
