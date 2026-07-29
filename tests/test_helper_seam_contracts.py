from __future__ import annotations

from src import crud_core_helpers
from src import crud_runtime_helpers
from src.domain import auth_service
from types import SimpleNamespace


def test_runtime_update_fields_wrapper_contract_is_current(monkeypatch):
    captured = {}

    def fake_validate_update_fields_from_crud(
        *, entity_name, updates, allowed_fields, **_ignored
    ):
        captured.update(
            {
                "entity_name": entity_name,
                "updates": updates,
                "allowed_fields": allowed_fields,
            }
        )
        return None

    monkeypatch.setattr(
        crud_core_helpers,
        "validate_update_fields_from_crud",
        fake_validate_update_fields_from_crud,
    )

    crud_runtime_helpers._validate_update_fields(
        "goal", {"title": "v1"}, {"title", "description"}
    )

    assert captured == {
        "entity_name": "goal",
        "updates": {"title": "v1"},
        "allowed_fields": {"title", "description"},
    }


def test_runtime_node_payload_wrapper_contract_is_current(monkeypatch):
    captured = {}

    def fake_node_from_backend_payload_from_crud(*, payload, **_ignored):
        captured.update({"payload": payload})
        return {"wrapped": True}

    monkeypatch.setattr(
        crud_core_helpers,
        "node_from_backend_payload_from_crud",
        fake_node_from_backend_payload_from_crud,
    )

    payload = {"id": 1}
    assert crud_runtime_helpers._node_from_backend_payload(payload) == {"wrapped": True}
    assert captured == {"payload": payload}


def test_auth_service_contracts_do_not_send_stale_kwargs(monkeypatch):
    captured = {}
    fake_payload = object()
    fake_node_result = {"ok": True}

    def fake_node_from_backend_payload_from_crud(*, payload, **_ignored):
        captured["node_payload"] = payload
        return fake_node_result

    def fake_validate_update_fields_from_crud(
        *, entity_name, updates, allowed_fields, **_ignored
    ):
        captured["validate"] = {
            "entity_name": entity_name,
            "updates": updates,
            "allowed_fields": allowed_fields,
        }

    monkeypatch.setattr(
        crud_core_helpers,
        "node_from_backend_payload_from_crud",
        fake_node_from_backend_payload_from_crud,
    )
    monkeypatch.setattr(
        crud_core_helpers,
        "validate_update_fields_from_crud",
        fake_validate_update_fields_from_crud,
    )

    assert (
        auth_service.node_from_backend_payload_from_crud(
            crud_module=object(), payload=fake_payload
        )
        is fake_node_result
    )
    auth_service.validate_update_fields_from_crud(
        crud_module=object(),
        entity_name="task",
        updates={"x": 1},
        allowed_fields={"x"},
    )

    assert captured["node_payload"] is fake_payload
    assert captured["validate"] == {
        "entity_name": "task",
        "updates": {"x": 1},
        "allowed_fields": {"x"},
    }


def test_auth_service_read_wrappers_delegate_to_read_service(monkeypatch):
    captured = []

    def _record(name):
        def _fn(**kwargs):
            captured.append((name, kwargs))
            return name

        return _fn

    fake_read_service = SimpleNamespace(
        get_user_by_username_from_crud=_record("get_user_by_username_from_crud"),
        get_user_by_id_from_crud=_record("get_user_by_id_from_crud"),
        get_all_users_from_crud=_record("get_all_users_from_crud"),
        get_team_members_from_crud=_record("get_team_members_from_crud"),
        get_user_goals_from_crud=_record("get_user_goals_from_crud"),
    )
    monkeypatch.setattr(
        auth_service,
        "_read_service_context",
        lambda: fake_read_service,
    )

    dummy_module = object()
    assert auth_service.get_user_by_username_from_crud(
        crud_module=dummy_module, username="alice"
    ) == "get_user_by_username_from_crud"
    assert auth_service.get_user_by_id_from_crud(
        crud_module=dummy_module, user_id=7
    ) == "get_user_by_id_from_crud"
    assert auth_service.get_all_users_from_crud(crud_module=dummy_module) == "get_all_users_from_crud"
    assert auth_service.get_team_members_from_crud(
        crud_module=dummy_module, manager_id=3
    ) == "get_team_members_from_crud"
    assert auth_service.get_user_goals_from_crud(
        crud_module=dummy_module, username="alice", cycle_id=1
    ) == "get_user_goals_from_crud"

    assert captured == [
        ("get_user_by_username_from_crud", {"crud_module": dummy_module, "username": "alice"}),
        ("get_user_by_id_from_crud", {"crud_module": dummy_module, "user_id": 7}),
        ("get_all_users_from_crud", {"crud_module": dummy_module}),
        ("get_team_members_from_crud", {"crud_module": dummy_module, "manager_id": 3}),
        (
            "get_user_goals_from_crud",
            {"crud_module": dummy_module, "username": "alice", "cycle_id": 1},
        ),
    ]
