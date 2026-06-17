from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend_app.schemas import (
    AtlasSnapshotRequest,
    LoginRequest,
    NodeDeleteResponse,
    NodeMutationView,
    NodeUpdateRequest,
    TaskCreateRequest,
    TimerStartRequest,
    TimerStopRequest,
)

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "docs" / "fixtures" / "hybrid_frontend"
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_manifest() -> list[dict[str, Any]]:
    payload = _load_json(FIXTURE_DIR / "manifest.json")
    assert isinstance(payload, list), "Fixture manifest must be a list."
    assert payload, "Fixture manifest must not be empty."
    return payload


def _parse_iso_datetime(value: Any) -> datetime:
    assert isinstance(value, str), f"Expected ISO datetime string, got {type(value)!r}."
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_task_shape(task: dict[str, Any]) -> None:
    for required in (
        "id",
        "title",
        "description",
        "progress",
        "deadline",
        "timer_started_at",
        "status",
        "total_time_spent",
        "assignee_id",
    ):
        assert required in task
    assert isinstance(task["id"], int) and task["id"] > 0
    assert isinstance(task["title"], str)
    assert isinstance(task["description"], str)
    assert isinstance(task["progress"], int)
    assert isinstance(task["status"], str) and task["status"]
    assert isinstance(task["total_time_spent"], int)
    if task["deadline"] is not None:
        _parse_iso_datetime(task["deadline"])
    if task["timer_started_at"] is not None:
        _parse_iso_datetime(task["timer_started_at"])
    if task["assignee_id"] is not None:
        assert isinstance(task["assignee_id"], int) and task["assignee_id"] > 0


def _assert_kr_shape(kr: dict[str, Any]) -> None:
    for required in (
        "id",
        "title",
        "description",
        "progress",
        "start_value",
        "target_value",
        "current_value",
        "metric_type",
        "weight",
        "unit",
        "tasks",
    ):
        assert required in kr
    assert isinstance(kr["id"], int) and kr["id"] > 0
    assert isinstance(kr["title"], str)
    assert isinstance(kr["description"], str)
    assert isinstance(kr["progress"], int)
    assert isinstance(kr["metric_type"], str) and kr["metric_type"]
    assert isinstance(kr["tasks"], list)
    if kr.get("ai_overall_score") is not None:
        assert isinstance(kr["ai_overall_score"], int)
    if kr.get("ai_deadline_state") is not None:
        assert isinstance(kr["ai_deadline_state"], str)
    for task in kr["tasks"]:
        assert isinstance(task, dict)
        _assert_task_shape(task)


def _assert_objective_shape(objective: dict[str, Any]) -> None:
    for required in (
        "id",
        "title",
        "description",
        "progress",
        "score_mode",
        "weight",
        "key_results",
    ):
        assert required in objective
    assert isinstance(objective["id"], int) and objective["id"] > 0
    assert isinstance(objective["title"], str)
    assert isinstance(objective["description"], str)
    assert isinstance(objective["progress"], int)
    assert isinstance(objective["key_results"], list)
    for kr in objective["key_results"]:
        assert isinstance(kr, dict)
        _assert_kr_shape(kr)


def _assert_goal_shape(goal: dict[str, Any]) -> None:
    for required in ("id", "title", "description", "progress", "owner_id", "objectives"):
        assert required in goal
    assert isinstance(goal["id"], int) and goal["id"] > 0
    assert isinstance(goal["title"], str)
    assert isinstance(goal["description"], str)
    assert isinstance(goal["progress"], int)
    assert isinstance(goal["owner_id"], int) and goal["owner_id"] > 0
    assert isinstance(goal["objectives"], list)
    for objective in goal["objectives"]:
        assert isinstance(objective, dict)
        _assert_objective_shape(objective)


def _assert_snapshot_shape(snapshot: dict[str, Any]) -> None:
    assert "goals" in snapshot
    assert "users_map" in snapshot
    goals = snapshot["goals"]
    users_map = snapshot["users_map"]

    assert isinstance(goals, list)
    assert isinstance(users_map, dict)

    for owner_id, display_name in users_map.items():
        int(owner_id)
        assert isinstance(display_name, str) and display_name.strip()

    for goal in goals:
        assert isinstance(goal, dict)
        _assert_goal_shape(goal)


def test_hybrid_frontend_fixture_manifest_entries_are_valid() -> None:
    entries = _load_manifest()
    seen_ids: set[str] = set()

    for entry in entries:
        assert isinstance(entry, dict)
        fixture_id = str(entry.get("id") or "").strip()
        method = str(entry.get("method") or "").strip()
        path = str(entry.get("path") or "").strip()
        request_name = str(entry.get("request") or "").strip()
        response_name = str(entry.get("response") or "").strip()

        assert fixture_id
        assert fixture_id not in seen_ids
        seen_ids.add(fixture_id)

        assert method in {"GET", "POST", "PATCH", "PUT", "DELETE"}
        assert path.startswith("/v1/")
        assert request_name.endswith(".json")
        assert response_name.endswith(".json")

        assert (FIXTURE_DIR / request_name).exists()
        assert (FIXTURE_DIR / response_name).exists()

        _load_json(FIXTURE_DIR / request_name)
        _load_json(FIXTURE_DIR / response_name)


def test_hybrid_frontend_request_fixtures_match_backend_schemas() -> None:
    request_schemas = {
        "auth_login": LoginRequest,
        "atlas_snapshot": AtlasSnapshotRequest,
        "timer_start": TimerStartRequest,
        "timer_stop": TimerStopRequest,
        "node_update": NodeUpdateRequest,
        "node_create": TaskCreateRequest,
        "node_delete": None,
    }

    entries = _load_manifest()
    assert {entry["id"] for entry in entries} == set(request_schemas)

    for entry in entries:
        fixture_id = str(entry["id"])
        request_payload = _load_json(FIXTURE_DIR / str(entry["request"]))
        schema = request_schemas[fixture_id]
        if schema is None:
            assert isinstance(request_payload, dict)
            continue
        validated = schema.model_validate(request_payload)
        assert validated is not None


def test_hybrid_frontend_response_fixtures_match_expected_shapes() -> None:
    responses = {
        str(entry["id"]): _load_json(FIXTURE_DIR / str(entry["response"]))
        for entry in _load_manifest()
    }

    auth_login = responses["auth_login"]
    assert isinstance(auth_login, dict)
    assert auth_login.get("success") is True
    assert auth_login.get("error_code") is None
    user = auth_login.get("user")
    assert isinstance(user, dict)
    assert isinstance(user.get("id"), int) and int(user["id"]) > 0
    assert isinstance(user.get("username"), str) and str(user["username"]).strip()
    assert isinstance(user.get("role"), str) and str(user["role"]).strip()

    snapshot = responses["atlas_snapshot"]
    assert isinstance(snapshot, dict)
    _assert_snapshot_shape(snapshot)

    timer_start = responses["timer_start"]
    assert isinstance(timer_start, dict)
    assert isinstance(timer_start.get("work_log_id"), int)
    assert isinstance(timer_start.get("task_id"), int)
    _parse_iso_datetime(timer_start.get("start_time"))

    timer_stop = responses["timer_stop"]
    assert isinstance(timer_stop, dict)
    assert isinstance(timer_stop.get("work_log_id"), int)
    assert isinstance(timer_stop.get("task_id"), int)
    assert isinstance(timer_stop.get("duration_minutes"), int)
    _parse_iso_datetime(timer_stop.get("start_time"))
    _parse_iso_datetime(timer_stop.get("end_time"))
    assert isinstance(timer_stop.get("summary"), str)

    node_update = responses["node_update"]
    assert isinstance(node_update, dict)
    node_view = NodeMutationView.model_validate(node_update)
    assert node_view.node_type == "KEY_RESULT"
    assert node_view.id == int(node_update["id"])

    node_create = responses["node_create"]
    assert isinstance(node_create, dict)
    created_node = NodeMutationView.model_validate(node_create)
    assert created_node.node_type == "TASK"
    assert created_node.id == int(node_create["id"])

    node_delete = responses["node_delete"]
    assert isinstance(node_delete, dict)
    deleted_node = NodeDeleteResponse.model_validate(node_delete)
    assert deleted_node.node_type == "TASK"
    assert deleted_node.id == int(node_delete["id"])
    assert deleted_node.deleted is True
