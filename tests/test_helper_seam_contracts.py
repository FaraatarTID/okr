from __future__ import annotations

from src import crud_core_helpers
from src import crud_runtime_helpers
from src.domain import auth_service


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
