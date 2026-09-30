from datetime import datetime
from types import SimpleNamespace


def _cycle(cycle_id: int, owner_manager_id: int | None):
    return SimpleNamespace(
        id=cycle_id,
        owner_manager_id=owner_manager_id,
        is_active=True,
        title=f"Cycle {cycle_id}",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 3, 31),
    )


def test_manager_cycle_visibility_includes_admin_cycles_but_not_other_managers():
    from backend_app.scope_resolution import _visible_cycles_for_scope

    scope = {
        "role": "manager",
        "is_admin": False,
        "actor_id": 20,
        "manager_id": None,
        "admin_ids": {1},
    }
    cycles = [_cycle(101, 20), _cycle(102, 1), _cycle(103, 30)]

    visible = _visible_cycles_for_scope(scope, cycles)

    assert [cycle.id for cycle in visible] == [101, 102]


def test_member_cycle_visibility_includes_admin_and_own_manager_cycles():
    from backend_app.scope_resolution import _visible_cycles_for_scope

    scope = {
        "role": "member",
        "is_admin": False,
        "actor_id": 40,
        "manager_id": 20,
        "admin_ids": {1},
    }
    cycles = [_cycle(101, 1), _cycle(102, 20), _cycle(103, 30)]

    visible = _visible_cycles_for_scope(scope, cycles)

    assert [cycle.id for cycle in visible] == [101, 102]


def test_api_create_cycle_forces_manager_to_own_cycle(monkeypatch):
    import backend_app.main_mutation_handlers as handlers

    captured = {}

    monkeypatch.setattr(
        handlers,
        "_require_admin_or_manager_actor_scope",
        lambda actor: None,
    )
    monkeypatch.setattr(
        handlers,
        "_resolve_scope_for_actor",
        lambda actor: {
            "is_admin": False,
            "role": "manager",
            "actor_id": 20,
        },
    )

    def _create_cycle(**kwargs):
        captured.update(kwargs)
        return _cycle(101, kwargs["owner_manager_id"])

    monkeypatch.setattr(handlers, "create_cycle", _create_cycle)

    payload = handlers.CycleCreateRequest(
        title="Manager cycle",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 3, 31),
        is_active=True,
        owner_manager_id=30,
    )

    result = handlers.api_create_cycle(payload, x_okr_actor="manager")

    assert result.id == 101
    assert captured["actor_username"] == "manager"
    assert captured["owner_manager_id"] == 20
