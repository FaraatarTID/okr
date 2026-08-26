"""DB-level enforcement tests for the per-manager active-cycle invariant.

The partial unique index `ux_cycle_owner_active` (baseline migration) ensures
at most one ACTIVE cycle per owner (owner_manager_id). Cycles with different
owners may each have their own active cycle.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import Session

from src.models import Cycle, User, UserRole


def _ensure_owners(engine, owner_ids: list[int]) -> None:
    """Insert manager users so cycle.owner_manager_id FK is satisfied."""
    with Session(engine) as session:
        for oid in owner_ids:
            if session.get(User, oid) is None:
                session.add(
                    User(
                        id=oid,
                        username=f"manager{oid}",
                        display_name=f"Manager {oid}",
                        password_hash="x",
                        role=UserRole.MANAGER,
                        is_active=True,
                    )
                )
        session.commit()


def _cycle(cid: int, title: str, is_active: bool, owner: int | None) -> Cycle:
    return Cycle(
        id=cid,
        title=title,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        is_active=is_active,
        owner_manager_id=owner,
    )


def test_second_active_cycle_same_owner_rejected(isolated_db):
    """Two active cycles with the SAME owner are rejected by the index."""
    from src.database import get_engine

    engine = get_engine()
    _ensure_owners(engine, [10])
    with Session(engine) as session:
        session.add(_cycle(1, "Q1", True, owner=10))
        session.commit()
        session.add(_cycle(2, "Q2", True, owner=10))
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


def test_active_cycles_different_owners_allowed(isolated_db):
    """Different owners may each have their own active cycle (per-scope model)."""
    from src.database import get_engine

    engine = get_engine()
    _ensure_owners(engine, [10, 20])
    with Session(engine) as session:
        session.add(_cycle(1, "Q1", True, owner=10))
        session.add(_cycle(2, "Q2", True, owner=20))
        session.commit()  # must not raise
        active = session.query(Cycle).filter(Cycle.is_active).all()
        assert sorted(c.owner_manager_id for c in active) == [10, 20]


def test_multiple_inactive_cycles_same_owner_allowed(isolated_db):
    """Only *active* cycles are constrained; inactive ones are unlimited."""
    from src.database import get_engine

    engine = get_engine()
    _ensure_owners(engine, [10])
    with Session(engine) as session:
        session.add(_cycle(1, "Q1", False, owner=10))
        session.add(_cycle(2, "Q2", False, owner=10))
        session.add(_cycle(3, "Q3", False, owner=10))
        session.commit()  # must not raise


def test_deactivate_then_activate_succeeds(isolated_db):
    """The normal deactivate-then-activate sequence remains possible."""
    from src.database import get_engine

    engine = get_engine()
    _ensure_owners(engine, [10])
    with Session(engine) as session:
        session.add(_cycle(1, "Q1", True, owner=10))
        session.commit()

        q1 = session.get(Cycle, 1)
        assert q1 is not None
        q1.is_active = False
        session.commit()

        session.add(_cycle(2, "Q2", True, owner=10))
        session.commit()

        active = session.query(Cycle).filter(Cycle.is_active).all()
        assert [c.id for c in active] == [2]


class _GuardCrudModule:
    """Minimal crud_module stand-in for the guard path."""

    Cycle = Cycle
    UserRole = None  # not reached: actor_username is None and proxy disabled

    @staticmethod
    def _backend_mutation_proxy_enabled():
        return False

    @staticmethod
    def select(*args, **kwargs):
        from sqlmodel import select

        return select(*args, **kwargs)

    @staticmethod
    def get_session_context():
        from src.database import get_session_context

        return get_session_context()


def test_last_active_cycle_guard_blocks_deactivation(isolated_db):
    """update_cycle_from_crud refuses to deactivate the owner's only active cycle."""
    from src.crud_cycle_helpers import update_cycle_from_crud, _is_last_active_cycle
    from src.database import get_engine

    engine = get_engine()
    _ensure_owners(engine, [10])
    with Session(engine) as session:
        session.add(_cycle(1, "Q1", True, owner=10))
        session.commit()

        crud_module = _GuardCrudModule()
        assert _is_last_active_cycle(
            crud_module=crud_module, session=session, exclude_cycle_id=1
        )

        with pytest.raises(ValueError, match="only active cycle"):
            update_cycle_from_crud(
                crud_module=crud_module,
                cycle_id=1,
                title="Q1",
                start_date=datetime(2026, 1, 1),
                end_date=datetime(2026, 12, 31),
                is_active=False,
                actor_username=None,
            )
