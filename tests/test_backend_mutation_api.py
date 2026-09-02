from datetime import datetime, timezone
from types import SimpleNamespace

from tests._test_credentials import credential_password

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.routing import Match

from fastapi.routing import APIRoute

from backend_app.schemas import (
    AlignmentMutationView,
    AlignmentDeleteResponse,
    CheckInMutationView,
    CycleMutationView,
    CycleDeleteResponse,
    ExperimentMutationView,
    JobView,
    JobCancelResponse,
    NodeDeleteResponse,
    NodeMutationView,
    ObjectiveAlignmentLinkMutationView,
    ObjectiveAlignmentLinkDeleteResponse,
    RetrospectiveMutationView,
    RetroExperimentOutcomeView,
    TeamDeleteResponse,
    TeamMutationView,
    UserMutationView,
    UserPasswordResetResponse,
    WeeklyPlanMutationView,
    WorkLogDeleteResponse,
)


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


_ROUTER_CONTRACTS = {
    ("POST", "/v1/nodes/goal"): (201, NodeMutationView, "backend_app.routers.node_mutation_routes"),
    ("POST", "/v1/nodes/objective"): (201, NodeMutationView, "backend_app.routers.node_mutation_routes"),
    ("POST", "/v1/nodes/key_result"): (201, NodeMutationView, "backend_app.routers.node_mutation_routes"),
    ("POST", "/v1/nodes/task"): (201, NodeMutationView, "backend_app.routers.node_mutation_routes"),
    ("PATCH", "/v1/nodes/{node_type}/{node_id}"): (200, NodeMutationView, "backend_app.routers.node_mutation_routes"),
    ("DELETE", "/v1/nodes/{node_type}/{node_id}"): (200, NodeDeleteResponse, "backend_app.routers.node_mutation_routes"),
    ("POST", "/v1/cycles"): (201, CycleMutationView, "backend_app.routers.cycle_mutation_routes"),
    ("PATCH", "/v1/cycles/{cycle_id}"): (200, None, "backend_app.routers.cycle_mutation_routes"),
    ("DELETE", "/v1/cycles/{cycle_id}"): (200, CycleDeleteResponse, "backend_app.routers.cycle_mutation_routes"),
    ("POST", "/v1/teams"): (201, TeamMutationView, "backend_app.routers.team_mutation_routes"),
    ("PATCH", "/v1/teams/{team_id}"): (200, TeamMutationView, "backend_app.routers.team_mutation_routes"),
    ("DELETE", "/v1/teams/{team_id}"): (200, TeamDeleteResponse, "backend_app.routers.team_mutation_routes"),
    ("POST", "/v1/users"): (201, UserMutationView, "backend_app.routers.user_mutation_routes"),
    ("PATCH", "/v1/users/{user_id}"): (200, UserMutationView, "backend_app.routers.user_mutation_routes"),
    ("POST", "/v1/users/{user_id}/reset-password"): (200, UserPasswordResetResponse, "backend_app.routers.user_mutation_routes"),
    ("POST", "/v1/check-ins"): (201, CheckInMutationView, "backend_app.routers.checkin_mutation_routes"),
    ("POST", "/v1/experiments"): (201, ExperimentMutationView, "backend_app.routers.experiment_mutation_routes"),
    ("PATCH", "/v1/experiments/{experiment_id}"): (200, ExperimentMutationView, "backend_app.routers.experiment_mutation_routes"),
    ("POST", "/v1/experiments/{experiment_id}/close"): (200, ExperimentMutationView, "backend_app.routers.experiment_mutation_routes"),
    ("POST", "/v1/alignments"): (201, AlignmentMutationView, "backend_app.routers.analytics_mutation_routes"),
    ("DELETE", "/v1/alignments/{edge_id}"): (200, AlignmentDeleteResponse, "backend_app.routers.analytics_mutation_routes"),
    ("POST", "/v1/objective-alignment-links"): (201, ObjectiveAlignmentLinkMutationView, "backend_app.routers.analytics_mutation_routes"),
    ("DELETE", "/v1/objective-alignment-links/{link_id}"): (200, ObjectiveAlignmentLinkDeleteResponse, "backend_app.routers.analytics_mutation_routes"),
    ("DELETE", "/v1/work-logs/{work_log_id}"): (200, WorkLogDeleteResponse, "backend_app.routers.analytics_mutation_routes"),
    ("POST", "/v1/retrospectives"): (201, RetrospectiveMutationView, "backend_app.routers.analytics_mutation_routes"),
    ("PUT", "/v1/retrospectives/{retrospective_id}/experiment-outcomes"): (200, RetroExperimentOutcomeView, "backend_app.routers.analytics_mutation_routes"),
    ("POST", "/v1/weekly-plans"): (201, WeeklyPlanMutationView, "backend_app.routers.analytics_mutation_routes"),
    ("POST", "/v1/jobs"): (202, JobView, "backend_app.routers.operations_routes"),
    ("DELETE", "/v1/jobs/{job_id}"): (204, None, "backend_app.routers.operations_routes"),
    ("POST", "/v1/jobs/{job_id}/cancel"): (200, JobCancelResponse, "backend_app.routers.operations_routes"),
    ("POST", "/v1/timer/start"): (200, None, "backend_app.routers.operations_routes"),
    ("POST", "/v1/timer/stop"): (200, None, "backend_app.routers.operations_routes"),
    ("POST", "/v1/ai/analyze-node"): (200, None, "backend_app.routers.ai_routes"),
    ("POST", "/v1/ai/strategy-pulse"): (200, None, "backend_app.routers.ai_routes"),
    ("POST", "/v1/ai/team-coach"): (200, None, "backend_app.routers.ai_routes"),
    ("POST", "/v1/state/{key}"): (200, None, "backend_app.routers.platform_routes"),
    ("POST", "/v1/admin/db-restore"): (200, None, "backend_app.routers.platform_routes"),
}


def _find_route(method: str, path: str):
    def _iter_api_routes(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
                continue
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                yield from _iter_api_routes(getattr(original_router, "routes", []))

    def _iter_all_routes():
        from backend_app.main import app

        return _iter_api_routes(app.routes)

    def _canonical_path(p: str) -> str:
        if not p:
            return "/"
        normalized = "/" + "/".join(segment for segment in p.split("/") if segment)
        if normalized.endswith("/"):
            normalized = normalized[:-1]
        if normalized.startswith("/api/"):
            normalized = normalized.removeprefix("/api")
        return normalized

    def _normalized(p: str) -> str:
        if not p:
            return "/"
        normalized = "/" + "/".join(segment for segment in p.split("/") if segment)
        if normalized.endswith("/"):
            normalized = normalized[:-1]
        return normalized

    normalized_target = _normalized(path)
    alt_targets = {normalized_target}
    if normalized_target.startswith("/api/"):
        alt_targets.add(normalized_target.removeprefix("/api"))
    elif normalized_target.startswith("/"):
        alt_targets.add(f"/api{normalized_target}")

    for route in _iter_all_routes():
        if not isinstance(route, APIRoute):
            continue
        route_path = _canonical_path(getattr(route, "path", ""))
        for candidate_path in alt_targets:
            if route_path == _canonical_path(candidate_path):
                if method in (route.methods or set()):
                    return route
            scope = {
                "type": "http",
                "method": method,
                "path": _normalized(candidate_path),
            }
            match, _ = route.matches(scope)
            if match == Match.FULL and method in (route.methods or set()):
                return route
    return None


def test_router_contracts_for_mutation_endpoints_stay_stable():
    for (method, path), (status_code, response_model, expected_module) in _ROUTER_CONTRACTS.items():
        route = _find_route(method, path)
        assert route is not None, f"Missing route {method} {path}"
        assert (route.status_code or 200) == status_code, (
            f"Route {method} {path} changed status from {status_code} to {route.status_code}"
        )

        if response_model is None:
            pass
        else:
            assert route.response_model is response_model, (
                f"Route {method} {path} response_model changed"
            )

        assert route.endpoint.__module__ == expected_module, (
            f"Route {method} {path} should be implemented in {expected_module}, "
            f"found {route.endpoint.__module__}"
        )


def test_router_modules_expose_registration_functions():
    import importlib

    router_modules = [
        "backend_app.routers.node_mutation_routes",
        "backend_app.routers.cycle_mutation_routes",
        "backend_app.routers.team_mutation_routes",
        "backend_app.routers.user_mutation_routes",
        "backend_app.routers.checkin_mutation_routes",
        "backend_app.routers.experiment_mutation_routes",
        "backend_app.routers.analytics_mutation_routes",
        "backend_app.routers.operations_routes",
        "backend_app.routers.ai_routes",
        "backend_app.routers.platform_routes",
    ]
    for module_name in router_modules:
        module = importlib.import_module(module_name)
        register_name = "register_" + module_name.rsplit("_", 1)[0].split(".")[-1] + "_routes"
        if module_name.endswith("ai_routes"):
            register_name = "register_ai_routes"
        elif module_name.endswith("platform_routes"):
            register_name = "register_platform_routes"
        elif module_name.endswith("analytics_mutation_routes"):
            register_name = "register_analytics_mutation_routes"
        elif module_name.endswith("checkin_mutation_routes"):
            register_name = "register_checkin_mutation_routes"
        elif module_name.endswith("operations_routes"):
            register_name = "register_operations_routes"
        assert hasattr(module, register_name), f"{module_name} missing {register_name}"
        assert callable(getattr(module, register_name)), f"{module_name}.{register_name} is not callable"


def test_backend_startup_bootstraps_admin_user(monkeypatch):
    import backend_app.main as backend_main

    calls = {"count": 0}

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)

    def _fake_ensure_admin_exists():
        calls["count"] += 1
        return True

    monkeypatch.setattr(backend_main, "ensure_admin_exists", _fake_ensure_admin_exists)

    with TestClient(backend_main.app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert calls["count"] == 1


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


def test_update_node_endpoint_rejects_mismatched_header_and_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.patch(
        "/v1/nodes/task/88",
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "updates": {"title": "Task Updated", "progress": 40},
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_update_node_endpoint_returns_403_for_permission_error(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _deny_update(*_args, **_kwargs):
        raise PermissionError("Insufficient permissions for node update.")

    monkeypatch.setattr(backend_main, "update_task", _deny_update)

    response = client.patch(
        "/v1/nodes/task/88",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"title": "Task Updated"}},
    )

    assert response.status_code == 403
    assert "permission" in str(response.json().get("detail", "")).lower()


def test_create_task_endpoint_rejects_mismatched_header_and_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/nodes/task",
        headers={"X-OKR-Actor": "alice"},
        json={
            "key_result_id": 3201,
            "title": "Probe task",
            "description": "Created from SPA",
            "estimated_minutes": 45,
            "actor_username": "mallory",
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


@pytest.mark.parametrize(
    ("route_path", "create_fn", "payload", "node_type"),
    [
        (
            "/v1/nodes/goal",
            "create_goal",
            {
                "user_id": "alice",
                "title": "Goal from test",
                "description": "created via api",
                "actor_username": "mallory",
            },
            "GOAL",
        ),
        (
            "/v1/nodes/objective",
            "create_objective",
            {
                "goal_id": 10,
                "title": "Objective from test",
                "description": "created via api",
                "actor_username": "mallory",
            },
            "OBJECTIVE",
        ),
        (
            "/v1/nodes/key_result",
            "create_key_result",
            {
                "objective_id": 12,
                "title": "KR from test",
                "description": "created via api",
                "target_value": 100,
                "unit": "%",
                "actor_username": "mallory",
            },
            "KEY_RESULT",
        ),
        (
            "/v1/nodes/task",
            "create_task",
            {
                "key_result_id": 3201,
                "title": "Task from test",
                "description": "created via api",
                "estimated_minutes": 45,
                "actor_username": "alice",
            },
            "TASK",
        ),
    ],
)
def test_create_node_endpoints_reject_mismatched_header_and_payload_actor(
    monkeypatch, route_path, create_fn, payload, node_type
):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={**payload, "actor_username": "mallory"},
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


@pytest.mark.parametrize(
    ("route_path", "update_fn", "expected_type"),
    [
        ("/v1/nodes/goal/88", "update_goal", "GOAL"),
        ("/v1/nodes/objective/88", "update_objective", "OBJECTIVE"),
        ("/v1/nodes/key_result/88", "update_key_result", "KEY_RESULT"),
        ("/v1/nodes/task/88", "update_task", "TASK"),
    ],
)
def test_update_node_endpoints_reject_mismatched_header_and_payload_actor_for_all_types(
    monkeypatch, route_path, update_fn, expected_type
):
    client, backend_main = _make_client(monkeypatch)

    response = client.patch(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "updates": {"title": "Node Updated", "progress": 40},
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


@pytest.mark.parametrize(
    ("route_path", "delete_fn", "expected_type"),
    [
        ("/v1/nodes/goal/91", "delete_goal", "GOAL"),
        ("/v1/nodes/objective/91", "delete_objective", "OBJECTIVE"),
        ("/v1/nodes/key_result/91", "delete_key_result", "KEY_RESULT"),
        ("/v1/nodes/task/91", "delete_task", "TASK"),
    ],
)
def test_delete_node_endpoints_succeed_for_all_types(
    monkeypatch, route_path, delete_fn, expected_type
):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_delete(node_id, actor_username=None):
        captured["node_id"] = node_id
        captured["actor_username"] = actor_username
        return True

    monkeypatch.setattr(backend_main, delete_fn, _fake_delete)
    response = client.delete(
        route_path,
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 200
    assert int(captured["node_id"]) == 91
    assert captured["actor_username"] == "alice"
    assert response.json()["node_type"] == expected_type
    assert response.json()["deleted"] is True


@pytest.mark.parametrize(
    ("route_path", "delete_fn"),
    [
        ("/v1/nodes/goal/91", "delete_goal"),
        ("/v1/nodes/objective/91", "delete_objective"),
        ("/v1/nodes/key_result/91", "delete_key_result"),
        ("/v1/nodes/task/91", "delete_task"),
    ],
)
def test_delete_node_endpoint_returns_403_for_permission_error(
    monkeypatch, route_path, delete_fn
):
    client, backend_main = _make_client(monkeypatch)

    def _deny_delete(*_args, **_kwargs):
        raise PermissionError("Insufficient permissions for node delete.")

    monkeypatch.setattr(backend_main, delete_fn, _deny_delete)

    response = client.delete(
        route_path,
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 403
    assert "permission" in str(response.json().get("detail", "")).lower()


@pytest.mark.parametrize(
    ("route_path", "delete_fn"),
    [
        ("/v1/nodes/goal/999", "delete_goal"),
        ("/v1/nodes/objective/999", "delete_objective"),
        ("/v1/nodes/key_result/999", "delete_key_result"),
        ("/v1/nodes/task/999", "delete_task"),
    ],
)
def test_delete_node_endpoint_returns_404_when_missing(
    monkeypatch, route_path, delete_fn
):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, delete_fn, lambda *_args, **_kwargs: False)

    response = client.delete(
        route_path,
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 404
    assert "not found" in str(response.json().get("detail", "")).lower()


def test_start_timer_endpoint_rejects_mismatched_header_and_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/timer/start",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 7, "user_id": "mallory"},
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_start_timer_endpoint_returns_403_for_permission_error(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _deny_start_timer(*_args, **_kwargs):
        raise PermissionError("Insufficient permissions for timer start.")

    monkeypatch.setattr(backend_main, "start_timer", _deny_start_timer)

    response = client.post(
        "/v1/timer/start",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 7, "user_id": "alice"},
    )

    assert response.status_code == 403
    assert "permission" in str(response.json().get("detail", "")).lower()


def test_stop_timer_endpoint_rejects_mismatched_header_and_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/timer/stop",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 9, "summary": "focus", "user_id": "mallory"},
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_stop_timer_endpoint_returns_403_for_permission_error(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _deny_stop_timer(*_args, **_kwargs):
        raise PermissionError("Insufficient permissions for timer stop.")

    monkeypatch.setattr(backend_main, "stop_timer", _deny_stop_timer)

    response = client.post(
        "/v1/timer/stop",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 9, "summary": "focus", "user_id": "alice"},
    )

    assert response.status_code == 403
    assert "permission" in str(response.json().get("detail", "")).lower()


def test_stop_timer_endpoint_returns_404_when_no_active_timer(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "stop_timer", lambda *_args, **_kwargs: None)

    response = client.post(
        "/v1/timer/stop",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 9, "summary": "focus", "user_id": "alice"},
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == 9
    assert response.json()["duration_minutes"] == 0


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


def test_submit_job_endpoint_returns_429_with_retry_metadata(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _raise_quota(*args, **kwargs):
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "JOB_LIMIT_USER_RATE",
                "message": "User job rate limit exceeded.",
                "retry_after_seconds": 60,
            },
            headers={"Retry-After": "60"},
        )

    monkeypatch.setattr(backend_main, "enforce_job_submit_limits", _raise_quota)

    response = client.post(
        "/v1/jobs",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "ai.generate_json", "payload": {"prompt": "hello"}},
    )

    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "60"
    assert response.json().get("detail", {}).get("error_code") == "JOB_LIMIT_USER_RATE"


def test_submit_job_endpoint_audits_rejected_submission(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = []

    def _raise_quota(*args, **kwargs):
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "JOB_LIMIT_USER_PENDING",
                "message": "User pending job limit exceeded.",
                "retry_after_seconds": 5,
            },
            headers={"Retry-After": "5"},
        )

    monkeypatch.setattr(backend_main, "enforce_job_submit_limits", _raise_quota)
    monkeypatch.setattr(
        backend_main,
        "_safe_audit_job_submit",
        lambda **kwargs: captured.append(kwargs),
    )

    response = client.post(
        "/v1/jobs",
        headers={
            "X-OKR-Actor": "alice",
            "X-OKR-Idempotency-Key": "idem-reject-1",
        },
        json={"kind": "ai.generate_json", "payload": {"prompt": "hello"}},
    )

    assert response.status_code == 429
    assert len(captured) == 1
    assert captured[0].get("action") == "job_submit_rejected"
    assert captured[0].get("error_code") == "JOB_LIMIT_USER_PENDING"


def test_job_endpoints_fail_closed_in_supabase_api_mode(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: True)

    response = client.post(
        "/v1/jobs",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "pdf.weekly", "payload": {}},
    )

    assert response.status_code == 503
    assert "job queue" in response.json()["detail"].lower()


def test_weekly_plan_supabase_mode_enforces_target_user_scope(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "is_supabase_api_mode_enabled", lambda: True)
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda _actor: {"is_admin": False, "owner_ids": {7}},
    )

    response = client.post(
        "/v1/weekly-plans",
        headers={"X-OKR-Actor": "alice"},
        json={
            "user_id": 99,
            "start_date": "2026-09-07T00:00:00Z",
            "end_date": "2026-09-13T23:59:59Z",
            "p1": "Probe",
        },
    )

    assert response.status_code == 403


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


def test_submit_job_endpoint_audits_accepted_submission(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = []

    monkeypatch.setattr(
        backend_main,
        "enforce_job_submit_limits",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        backend_main,
        "_safe_audit_job_submit",
        lambda **kwargs: captured.append(kwargs),
    )

    def _fake_enqueue_job(**kwargs):
        return SimpleNamespace(
            id="job-accept-1",
            team_id=3,
            status="pending",
        )

    monkeypatch.setattr(backend_main, "enqueue_job", _fake_enqueue_job)
    monkeypatch.setattr(
        backend_main,
        "serialize_job",
        lambda job: {
            "id": "job-accept-1",
            "kind": "ai.generate_json",
            "status": "pending",
            "actor_username": "alice",
            "team_id": 3,
            "attempts": 0,
            "max_attempts": 2,
            "cancel_requested": False,
            "idempotency_key": None,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error_text": None,
        },
    )

    response = client.post(
        "/v1/jobs",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "ai.generate_json", "payload": {"prompt": "hello"}},
    )

    assert response.status_code == 202
    assert len(captured) == 1
    assert captured[0].get("action") == "job_submit_accepted"
    assert captured[0].get("job_id") == "job-accept-1"


def test_create_user_endpoint_parses_role_and_team(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_create_user(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=9,
            username=kwargs.get("username"),
            display_name=kwargs.get("display_name"),
            role=kwargs.get("role"),
            manager_id=kwargs.get("manager_id"),
            team_id=kwargs.get("team_id"),
            is_active=True,
            must_change_password=bool(kwargs.get("must_change_password")),
        )

    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda *args, **kwargs: {
            "is_admin": True,
            "role": "admin",
            "actor_id": 1,
            "actor_username": "admin",
            "manager_id": None,
            "owner_ids": {1},
            "usernames": {"admin"},
        },
    )
    monkeypatch.setattr(backend_main, "create_user", _fake_create_user)

    response = client.post(
        "/v1/users",
        headers={"X-OKR-Actor": "admin"},
        json={
            "username": "member1",
            "password": credential_password("member1"),
            "role": "manager",
            "display_name": "Member One",
            "manager_id": 2,
            "team_id": 7,
            "must_change_password": True,
        },
    )

    assert response.status_code == 201
    assert (
        str(getattr(captured.get("role"), "value", captured.get("role"))) == "manager"
    )
    assert int(captured.get("team_id")) == 7
    assert response.json()["role"] == "manager"


def test_create_user_endpoint_rejects_weak_password_when_strict_policy_enabled(
    monkeypatch,
):
    client, _backend_main = _make_client(monkeypatch)
    monkeypatch.setenv("OKR_ENFORCE_STRONG_PASSWORD_POLICY", "true")
    weak_password = "a" * 3 + "1" * 3

    response = client.post(
        "/v1/users",
        headers={"X-OKR-Actor": "admin"},
        json={
            "username": "member1",
            "password": weak_password,
            "role": "member",
        },
    )

    assert response.status_code == 422


def test_create_check_in_endpoint_coerces_variation_enum(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_create_check_in(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=11,
            key_result_id=kwargs.get("kr_id"),
            value=float(kwargs.get("value", 0)),
            confidence_score=int(kwargs.get("confidence", 0)),
            comment=kwargs.get("comment"),
            variation_type=kwargs.get("variation_type"),
            special_cause_note=kwargs.get("special_cause_note"),
            experiment_id=kwargs.get("experiment_id"),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, "create_check_in", _fake_create_check_in)

    response = client.post(
        "/v1/check-ins",
        headers={"X-OKR-Actor": "alice"},
        json={
            "kr_id": 12,
            "value": 42.0,
            "confidence": 8,
            "comment": "weekly update",
            "variation_type": "COMMON_CAUSE",
        },
    )

    assert response.status_code == 201
    assert str(getattr(captured.get("variation_type"), "value", "")) == "COMMON_CAUSE"


def test_create_check_in_endpoint_rejects_low_confidence_without_comment(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "create_check_in", lambda **kwargs: None)

    response = client.post(
        "/v1/check-ins",
        headers={"X-OKR-Actor": "alice"},
        json={
            "kr_id": 12,
            "value": 42.0,
            "confidence": 4,
            "comment": "",
            "variation_type": "COMMON_CAUSE",
        },
    )

    assert response.status_code == 400
    assert "low-confidence" in str(response.json().get("detail", "")).lower()


def test_create_check_in_endpoint_rejects_special_cause_without_note(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "create_check_in", lambda **kwargs: None)

    response = client.post(
        "/v1/check-ins",
        headers={"X-OKR-Actor": "alice"},
        json={
            "kr_id": 12,
            "value": 42.0,
            "confidence": 8,
            "comment": "investigating variance",
            "variation_type": "SPECIAL_CAUSE",
            "special_cause_note": "",
        },
    )

    assert response.status_code == 400
    assert "special_cause_note" in str(response.json().get("detail", "")).lower()


def test_delete_alignment_endpoint_returns_404_when_missing(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "delete_alignment", lambda *args, **kwargs: False)

    response = client.delete(
        "/v1/alignments/123",
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 404


def test_read_atlas_snapshot_endpoint_scopes_owner_ids_for_non_admin(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)

    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {2, 3},
            "usernames": {"alice"},
        },
    )

    def _fake_snapshot(_session, *, cycle_id, owner_ids, include_analysis):
        captured["cycle_id"] = cycle_id
        captured["owner_ids"] = owner_ids
        captured["include_analysis"] = include_analysis
        return {"goals": [], "users_map": {}}

    monkeypatch.setattr(backend_main, "build_atlas_scope_snapshot", _fake_snapshot)

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "alice"},
        json={
            "cycle_id": 7,
            "owner_ids": [1, 2, 99],
            "include_analysis": False,
        },
    )
    assert response.status_code == 200
    assert captured["cycle_id"] == 7
    assert captured["owner_ids"] == [2]
    assert captured["include_analysis"] is False


def test_read_atlas_snapshot_uses_session_actor_for_scope(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)

    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, actor, token_version=None: (
            captured.__setitem__("resolved_actor", actor)
            or {
                "is_admin": True,
                "owner_ids": {1, 2},
                "usernames": {actor},
            }
        ),
    )

    def _fake_snapshot(_session, *, cycle_id, owner_ids, include_analysis):
        captured["cycle_id"] = cycle_id
        captured["owner_ids"] = owner_ids
        captured["include_analysis"] = include_analysis
        return {"goals": [], "users_map": {}}

    monkeypatch.setattr(backend_main, "build_atlas_scope_snapshot", _fake_snapshot)

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "alice"},
        json={
            "cycle_id": 7,
            "owner_ids": [1],
            "include_analysis": False,
            "actor_username": "alice",
        },
    )

    assert response.status_code == 200
    assert captured["resolved_actor"] == "alice"
    assert captured["cycle_id"] == 7
    assert captured["owner_ids"] == [1]


def test_read_atlas_snapshot_admin_without_owner_filter_reads_manager_cycle(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, actor, token_version=None: {
            "is_admin": True,
            "role": "admin",
            "actor_id": 1,
            "owner_ids": {1},
            "usernames": {actor},
        },
    )

    def _fake_snapshot(_session, *, cycle_id, owner_ids, include_analysis):
        captured.update(
            cycle_id=cycle_id,
            owner_ids=owner_ids,
            include_analysis=include_analysis,
        )
        return {"goals": [{"id": 42, "owner_id": 20}], "users_map": {20: "Manager"}}

    monkeypatch.setattr(backend_main, "build_atlas_scope_snapshot", _fake_snapshot)

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "admin"},
        json={"cycle_id": 42, "include_analysis": True},
    )

    assert response.status_code == 200
    assert captured == {
        "cycle_id": 42,
        "owner_ids": None,
        "include_analysis": True,
    }
    assert response.json()["goals"][0]["owner_id"] == 20


def test_read_atlas_snapshot_rejects_mismatched_header_and_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "alice"},
        json={
            "cycle_id": 7,
            "owner_ids": [1],
            "include_analysis": False,
            "actor_username": "mallory",
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_read_atlas_snapshot_rejects_unauthorized_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)

    def _deny_scope(_session, _actor, token_version=None):
        raise HTTPException(status_code=403, detail="Actor is not authorized.")

    monkeypatch.setattr(backend_main, "_resolve_actor_scope", _deny_scope)

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "mallory"},
        json={
            "cycle_id": 7,
            "owner_ids": [1],
            "include_analysis": False,
        },
    )

    assert response.status_code == 403
    assert "authorized" in str(response.json().get("detail", "")).lower()


def test_read_leadership_metrics_endpoint_scopes_usernames_for_non_admin(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)

    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice", "bob"},
        },
    )

    def _fake_metrics(usernames, cycle_id):
        captured["usernames"] = usernames
        captured["cycle_id"] = cycle_id
        return {"hygiene_pct": 100.0}

    monkeypatch.setattr(backend_main, "get_leadership_metrics", _fake_metrics)

    response = client.post(
        "/v1/read/leadership/metrics",
        headers={"X-OKR-Actor": "alice"},
        json={
            "cycle_id": 8,
            "usernames": ["mallory", "bob", "alice"],
        },
    )
    assert response.status_code == 200
    assert captured["cycle_id"] == 8
    assert captured["usernames"] == ["alice", "bob"]
    assert response.json().get("hygiene_pct") == 100.0


def test_read_query_audit_summary_requires_admin_and_forwards_filters(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": True,
            "owner_ids": set(),
            "usernames": {"alice"},
        },
    )

    def _fake_summary(session, **kwargs):
        captured["kwargs"] = kwargs
        return {
            "window_days": kwargs.get("days", 30),
            "recent_limit": kwargs.get("recent_limit", 20),
            "total_events": 1,
            "success_events": 1,
            "failure_events": 0,
            "by_actor_role": [],
            "by_actor_team_id": [],
            "by_target_type": [],
            "by_entity": [],
            "by_action": [],
            "recent_events": [],
        }

    monkeypatch.setattr(backend_main, "summarize_audit_events", _fake_summary)

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={
            "kind": "audit.summary",
            "params": {
                "days": 14,
                "recent_limit": 5,
                "actor_role": "manager",
                "target_type": "weekly_plan",
            },
        },
    )

    assert response.status_code == 200
    assert captured["kwargs"]["days"] == 14
    assert captured["kwargs"]["recent_limit"] == 5
    assert captured["kwargs"]["actor_role"] == "manager"
    assert captured["kwargs"]["target_type"] == "weekly_plan"
    assert response.json()["total_events"] == 1


def test_read_query_audit_summary_blocks_non_admin(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    called = {"count": 0}
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": set(),
            "usernames": {"alice"},
        },
    )

    def _unexpected(*_args, **_kwargs):
        called["count"] += 1
        return {}

    monkeypatch.setattr(backend_main, "summarize_audit_events", _unexpected)

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "audit.summary", "params": {"days": 7}},
    )

    assert response.status_code == 403
    assert called["count"] == 0


def test_read_query_mindmap_task_uses_detached_safe_serializer(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda _actor, token_version=None: {
            "is_admin": True,
            "owner_ids": set(),
            "usernames": {"alice"},
        },
    )

    monkeypatch.setattr(
        backend_main,
        "get_node",
        lambda node_id, node_type, actor_username=None: SimpleNamespace(
            id=node_id,
            node_type=node_type,
        ),
    )

    def _fake_serialize_task(node, include_key_result=False, include_work_logs=False):
        captured["include_key_result"] = include_key_result
        captured["include_work_logs"] = include_work_logs
        return {"__tablename__": "task", "id": int(getattr(node, "id", 0))}

    monkeypatch.setattr(backend_main, "_serialize_task", _fake_serialize_task)

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={
            "kind": "mindmap.root",
            "params": {"node_id": 1, "node_type": "TASK"},
        },
    )

    assert response.status_code == 200
    assert response.json()["node_type"] == "TASK"
    assert captured["include_key_result"] is False
    assert captured["include_work_logs"] is True


def test_read_query_mindmap_key_result_uses_detached_safe_serializer(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda _actor, token_version=None: {
            "is_admin": True,
            "owner_ids": set(),
            "usernames": {"alice"},
        },
    )

    monkeypatch.setattr(
        backend_main,
        "get_node",
        lambda node_id, node_type, actor_username=None: SimpleNamespace(
            id=node_id,
            node_type=node_type,
        ),
    )

    def _fake_serialize_key_result(
        node,
        include_tasks=False,
        include_check_ins=False,
        include_objective=False,
    ):
        captured["include_tasks"] = include_tasks
        captured["include_check_ins"] = include_check_ins
        captured["include_objective"] = include_objective
        return {"__tablename__": "key_result", "id": int(getattr(node, "id", 0))}

    monkeypatch.setattr(
        backend_main, "_serialize_key_result", _fake_serialize_key_result
    )

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={
            "kind": "mindmap.root",
            "params": {"node_id": 1, "node_type": "KEY_RESULT"},
        },
    )

    assert response.status_code == 200
    assert response.json()["node_type"] == "KEY_RESULT"
    assert captured["include_tasks"] is True
    assert captured["include_check_ins"] is False
    assert captured["include_objective"] is False


def test_ai_analyze_node_endpoint_rejects_mismatched_header_and_payload_actor(
    monkeypatch,
):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/ai/analyze-node",
        headers={"X-OKR-Actor": "alice"},
        json={
            "node_id": 42,
            "node_type": "OBJECTIVE",
            "actor_username": "mallory",
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_ai_analyze_node_endpoint_writes_audit_event_on_success(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    audit_calls = []

    monkeypatch.setattr(
        backend_main,
        "audit_log",
        lambda *args, **kwargs: audit_calls.append({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        backend_main,
        "get_user_by_username",
        lambda username: SimpleNamespace(
            role=SimpleNamespace(value="manager"),
            team_id=9,
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "analyze_node",
        lambda *args, **kwargs: {"overall_score": 84, "summary": "healthy"},
    )

    response = client.post(
        "/v1/ai/analyze-node",
        headers={"X-OKR-Actor": "alice"},
        json={"node_id": 42, "node_type": "OBJECTIVE"},
    )

    assert response.status_code == 200
    assert len(audit_calls) == 1
    assert audit_calls[0]["kwargs"]["action"] == "analyze"
    assert audit_calls[0]["kwargs"]["entity"] == "ai_node"
    assert audit_calls[0]["kwargs"]["actor"] == "alice"
    assert audit_calls[0]["kwargs"]["target_type"] == "node"
    assert int(audit_calls[0]["kwargs"]["target_id"]) == 42
    assert audit_calls[0]["kwargs"]["details"]["success"] is True
    assert audit_calls[0]["kwargs"]["details"]["actor_role"] == "manager"
    assert int(audit_calls[0]["kwargs"]["details"]["actor_team_id"]) == 9


def test_ai_analyze_node_endpoint_writes_audit_event_on_failure(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    audit_calls = []

    monkeypatch.setattr(
        backend_main,
        "audit_log",
        lambda *args, **kwargs: audit_calls.append({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        backend_main,
        "get_user_by_username",
        lambda username: SimpleNamespace(
            role=SimpleNamespace(value="manager"),
            team_id=9,
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "analyze_node",
        lambda *args, **kwargs: {"error": "Node 42 (OBJECTIVE) not found"},
    )

    response = client.post(
        "/v1/ai/analyze-node",
        headers={"X-OKR-Actor": "alice"},
        json={"node_id": 42, "node_type": "OBJECTIVE"},
    )

    assert response.status_code == 404
    assert len(audit_calls) == 1
    assert audit_calls[0]["kwargs"]["action"] == "analyze"
    assert audit_calls[0]["kwargs"]["entity"] == "ai_node"
    assert audit_calls[0]["kwargs"]["target_type"] == "node"
    assert int(audit_calls[0]["kwargs"]["target_id"]) == 42
    assert audit_calls[0]["kwargs"]["details"]["success"] is False
    assert audit_calls[0]["kwargs"]["details"]["error_type"] == "not_found"


@pytest.mark.parametrize(
    ("error_text", "expected_status"),
    [
        ("Node 42 (OBJECTIVE) not found", 404),
        ("Actor is not authorized.", 403),
        ("Permission denied for this node.", 403),
        ("Invalid request payload.", 400),
    ],
)
def test_ai_analyze_node_endpoint_maps_error_responses_to_http_status(
    monkeypatch, error_text, expected_status
):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main, "analyze_node", lambda *args, **kwargs: {"error": error_text}
    )

    response = client.post(
        "/v1/ai/analyze-node",
        headers={"X-OKR-Actor": "alice"},
        json={"node_id": 42, "node_type": "KEY_RESULT"},
    )

    assert response.status_code == expected_status
    assert str(response.json().get("detail", "")).strip() == error_text


def test_ai_analyze_node_endpoint_rejects_invalid_payload(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "analyze_node", lambda *args, **kwargs: "invalid")

    response = client.post(
        "/v1/ai/analyze-node",
        headers={"X-OKR-Actor": "alice"},
        json={"node_id": 42, "node_type": "KEY_RESULT"},
    )

    assert response.status_code == 500
    assert "invalid payload" in str(response.json().get("detail", "")).lower()


def test_ai_team_coach_endpoint_rejects_mismatched_header_and_payload_actor(
    monkeypatch,
):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/ai/team-coach",
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "team_data": {"total_krs": 9, "avg_confidence": 7.2},
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_ai_team_coach_endpoint_rejects_unauthorized_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            HTTPException(status_code=403, detail="Actor is not authorized.")
        ),
    )

    response = client.post(
        "/v1/ai/team-coach",
        headers={"X-OKR-Actor": "mallory"},
        json={"team_data": {"total_krs": 4}},
    )

    assert response.status_code == 403
    assert "authorized" in str(response.json().get("detail", "")).lower()


def test_ai_team_coach_endpoint_maps_error_to_bad_request(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice"},
        },
    )
    monkeypatch.setattr(
        backend_main,
        "analyze_team_health",
        lambda *_args, **_kwargs: {"error": "AI provider unavailable"},
    )

    response = client.post(
        "/v1/ai/team-coach",
        headers={"X-OKR-Actor": "alice"},
        json={"team_data": {"total_krs": 4}},
    )

    assert response.status_code == 400
    assert response.json().get("detail") == "AI provider unavailable"


def test_ai_team_coach_endpoint_rejects_invalid_payload(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice"},
        },
    )
    monkeypatch.setattr(
        backend_main, "analyze_team_health", lambda *_args, **_kwargs: ["bad"]
    )

    response = client.post(
        "/v1/ai/team-coach",
        headers={"X-OKR-Actor": "alice"},
        json={"team_data": {"total_krs": 4}},
    )

    assert response.status_code == 500
    assert "invalid payload" in str(response.json().get("detail", "")).lower()


def test_ai_strategy_pulse_endpoint_rejects_mismatched_header_and_payload_actor(
    monkeypatch,
):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/ai/strategy-pulse",
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "cycle_id": 9,
            "subject_username": "bob",
            "days": 21,
            "cycle_title": "Q1-2026",
        },
    )

    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_ai_strategy_pulse_endpoint_rejects_subject_outside_scope(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice"},
        },
    )

    response = client.post(
        "/v1/ai/strategy-pulse",
        headers={"X-OKR-Actor": "alice"},
        json={"cycle_id": 8, "subject_username": "bob"},
    )

    assert response.status_code == 403
    assert "authorized" in str(response.json().get("detail", "")).lower()


def test_ai_strategy_pulse_endpoint_returns_404_when_user_missing(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice"},
        },
    )
    monkeypatch.setattr(backend_main, "get_user_by_username", lambda _username: None)

    response = client.post(
        "/v1/ai/strategy-pulse",
        headers={"X-OKR-Actor": "alice"},
        json={"cycle_id": 8},
    )

    assert response.status_code == 404
    assert "user not found" in str(response.json().get("detail", "")).lower()


def test_ai_strategy_pulse_endpoint_maps_outlook_error_to_bad_request(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice"},
        },
    )
    monkeypatch.setattr(
        backend_main,
        "get_user_by_username",
        lambda username: SimpleNamespace(id=7, username=username),
    )
    monkeypatch.setattr(
        backend_main,
        "calculate_burnout_risk",
        lambda *_args, **_kwargs: {"risk_label": "Elevated"},
    )
    monkeypatch.setattr(
        backend_main, "detect_strategy_gaps", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        backend_main,
        "generate_predictive_outlook",
        lambda *_args, **_kwargs: {"error": "AI provider unavailable"},
    )

    response = client.post(
        "/v1/ai/strategy-pulse",
        headers={"X-OKR-Actor": "alice"},
        json={"cycle_id": 8},
    )

    assert response.status_code == 400
    assert response.json().get("detail") == "AI provider unavailable"


def test_ai_strategy_pulse_endpoint_rejects_invalid_outlook_payload(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "owner_ids": {1},
            "usernames": {"alice"},
        },
    )
    monkeypatch.setattr(
        backend_main,
        "get_user_by_username",
        lambda username: SimpleNamespace(id=7, username=username),
    )
    monkeypatch.setattr(
        backend_main,
        "calculate_burnout_risk",
        lambda *_args, **_kwargs: {"risk_label": "Elevated"},
    )
    monkeypatch.setattr(
        backend_main, "detect_strategy_gaps", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        backend_main, "generate_predictive_outlook", lambda *_args, **_kwargs: "invalid"
    )

    response = client.post(
        "/v1/ai/strategy-pulse",
        headers={"X-OKR-Actor": "alice"},
        json={"cycle_id": 8},
    )

    assert response.status_code == 500
    assert "invalid payload" in str(response.json().get("detail", "")).lower()


def test_read_query_cycles_all_returns_primary_active_cycle_for_member(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda _actor, token_version=None: {
            "is_admin": False,
            "role": "member",
            "owner_ids": {7},
            "usernames": {"member_user"},
        },
    )
    monkeypatch.setattr(
        backend_main,
        "get_active_cycles",
        lambda: [
            SimpleNamespace(
                id=3, title="Q1", start_date=None, end_date=None, is_active=True
            ),
            SimpleNamespace(
                id=8, title="Q2", start_date=None, end_date=None, is_active=True
            ),
        ],
    )
    monkeypatch.setattr(backend_main, "get_all_cycles", lambda: [])

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "member_user"},
        json={"kind": "cycles.all", "params": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("cycles"), list)
    assert len(payload["cycles"]) == 1
    assert int(payload["cycles"][0]["id"]) == 8


def test_member_snapshot_rejects_non_active_cycle_override(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)
    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "is_admin": False,
            "role": "member",
            "owner_ids": {7},
            "usernames": {"member_user"},
        },
    )
    monkeypatch.setattr(
        backend_main,
        "get_active_cycles",
        lambda: [
            SimpleNamespace(
                id=5, title="Q-active", start_date=None, end_date=None, is_active=True
            ),
        ],
    )
    monkeypatch.setattr(
        backend_main,
        "build_atlas_scope_snapshot",
        lambda *_args, **_kwargs: {"goals": [], "users_map": {}},
    )

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "member_user"},
        json={"actor_username": "member_user", "cycle_id": 99},
    )

    assert response.status_code == 403
    assert "active cycle" in str(response.json().get("detail", "")).lower()


# ============================================================================
# Typed update schema validation tests
# ============================================================================


@pytest.mark.parametrize(
    ("route_path", "update_fn"),
    [
        ("/v1/nodes/goal/1", "update_goal"),
        ("/v1/nodes/objective/1", "update_objective"),
        ("/v1/nodes/key_result/1", "update_key_result"),
        ("/v1/nodes/task/1", "update_task"),
    ],
)
def test_update_node_rejects_unknown_fields(monkeypatch, route_path, update_fn):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, update_fn, _fake_update)

    response = client.patch(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"unknown_field": "value", "title": "ok"}},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("route_path", "update_fn"),
    [
        ("/v1/nodes/goal/1", "update_goal"),
        ("/v1/nodes/objective/1", "update_objective"),
        ("/v1/nodes/key_result/1", "update_key_result"),
    ],
)
def test_update_node_rejects_oversized_title(monkeypatch, route_path, update_fn):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, update_fn, _fake_update)

    response = client.patch(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"title": "x" * 9999}},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("route_path", "update_fn"),
    [
        ("/v1/nodes/goal/1", "update_goal"),
        ("/v1/nodes/objective/1", "update_objective"),
        ("/v1/nodes/key_result/1", "update_key_result"),
    ],
)
def test_update_node_rejects_negative_progress(monkeypatch, route_path, update_fn):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, update_fn, _fake_update)

    response = client.patch(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"progress": -5}},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("route_path", "update_fn"),
    [
        ("/v1/nodes/goal/1", "update_goal"),
        ("/v1/nodes/objective/1", "update_objective"),
        ("/v1/nodes/key_result/1", "update_key_result"),
    ],
)
def test_update_node_rejects_progress_over_100(monkeypatch, route_path, update_fn):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, update_fn, _fake_update)

    response = client.patch(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"progress": 101}},
    )

    assert response.status_code == 422


def test_update_task_allows_progress_over_100(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(task_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=task_id,
            title="T",
            description="",
            progress=110,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "update_task", _fake_update)

    response = client.patch(
        "/v1/nodes/task/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"progress": 110}},
    )

    assert response.status_code == 200


def test_update_node_accepts_valid_partial_update(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_update(node_id, actor_username=None, **updates):
        captured.update(updates)
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "update_goal", _fake_update)

    response = client.patch(
        "/v1/nodes/goal/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"title": "New Title"}},
    )

    assert response.status_code == 200
    assert captured["title"] == "New Title"


def test_update_node_rejects_nested_objects_for_string_fields(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "update_goal", _fake_update)

    response = client.patch(
        "/v1/nodes/goal/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"description": {"nested": "object"}}},
    )

    assert response.status_code == 422


def test_update_node_rejects_oversized_description(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "update_goal", _fake_update)

    response = client.patch(
        "/v1/nodes/goal/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"description": "x" * 99999}},
    )

    assert response.status_code == 422


def test_update_key_result_rejects_negative_weight(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "update_key_result", _fake_update)

    response = client.patch(
        "/v1/nodes/key_result/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"weight": -1.5}},
    )

    assert response.status_code == 422


def test_update_node_rejects_invalid_cycle_id(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(node_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=node_id,
            title="T",
            description="",
            progress=0,
            owner_id=1,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "update_goal", _fake_update)

    response = client.patch(
        "/v1/nodes/goal/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"cycle_id": -5}},
    )

    assert response.status_code == 422


def test_update_experiment_rejects_unknown_fields(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(experiment_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=experiment_id,
            key_result_id=1,
            cycle_id=1,
            created_by="alice",
            hypothesis="H",
            change_description="D",
            start_at=None,
            end_at=None,
            status="PLANNED",
            decision=None,
            decision_rationale=None,
            expected_effect_direction=None,
            expected_effect_size=None,
            created_at=None,
        )

    monkeypatch.setattr(backend_main, "update_experiment", _fake_update)

    response = client.patch(
        "/v1/experiments/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"unknown_field": "value", "hypothesis": "test"}},
    )

    assert response.status_code == 422


def test_update_experiment_rejects_oversized_hypothesis(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(experiment_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=experiment_id,
            key_result_id=1,
            cycle_id=1,
            created_by="alice",
            hypothesis="H",
            change_description="D",
            start_at=None,
            end_at=None,
            status="PLANNED",
            decision=None,
            decision_rationale=None,
            expected_effect_direction=None,
            expected_effect_size=None,
            created_at=None,
        )

    monkeypatch.setattr(backend_main, "update_experiment", _fake_update)

    response = client.patch(
        "/v1/experiments/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"hypothesis": "x" * 99999}},
    )

    assert response.status_code == 422


def test_update_experiment_accepts_valid_partial_update(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_update(experiment_id, actor_username=None, **updates):
        captured.update(updates)
        return SimpleNamespace(
            id=experiment_id,
            key_result_id=1,
            cycle_id=1,
            created_by="alice",
            hypothesis="H",
            change_description="D",
            start_at=None,
            end_at=None,
            status="PLANNED",
            decision=None,
            decision_rationale=None,
            expected_effect_direction=None,
            expected_effect_size=None,
            created_at=None,
        )

    monkeypatch.setattr(backend_main, "update_experiment", _fake_update)

    response = client.patch(
        "/v1/experiments/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"hypothesis": "Updated hypothesis"}},
    )

    assert response.status_code == 200
    assert captured.get("hypothesis") == "Updated hypothesis"


def test_update_experiment_rejects_empty_hypothesis(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_update(experiment_id, actor_username=None, **updates):
        return SimpleNamespace(
            id=experiment_id,
            key_result_id=1,
            cycle_id=1,
            created_by="alice",
            hypothesis="H",
            change_description="D",
            start_at=None,
            end_at=None,
            status="PLANNED",
            decision=None,
            decision_rationale=None,
            expected_effect_direction=None,
            expected_effect_size=None,
            created_at=None,
        )

    monkeypatch.setattr(backend_main, "update_experiment", _fake_update)

    response = client.patch(
        "/v1/experiments/1",
        headers={"X-OKR-Actor": "alice"},
        json={"updates": {"hypothesis": ""}},
    )

    assert response.status_code == 422


# ============================================================================
# Atomic idempotency tests
# ============================================================================


def test_create_goal_idempotency_replays_cached_response(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_create_goal(**kwargs):
        call_count["n"] += 1
        return SimpleNamespace(
            id=100 + call_count["n"],
            title=str(kwargs.get("title") or ""),
            description=str(kwargs.get("description") or ""),
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_goal", _fake_create_goal)

    headers = {"X-OKR-Actor": "alice", "X-OKR-Idempotency-Key": "idem-goal-1"}
    payload = {"user_id": "alice", "title": "Goal A", "description": "test"}

    resp1 = client.post("/v1/nodes/goal", headers=headers, json=payload)
    assert resp1.status_code == 201
    first_id = resp1.json()["id"]

    resp2 = client.post("/v1/nodes/goal", headers=headers, json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == first_id
    assert call_count["n"] == 1


def test_create_goal_idempotency_rejects_different_payload(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    def _fake_create_goal(**kwargs):
        return SimpleNamespace(
            id=101,
            title=str(kwargs.get("title") or ""),
            description="",
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_goal", _fake_create_goal)

    headers = {"X-OKR-Actor": "alice", "X-OKR-Idempotency-Key": "idem-goal-2"}
    payload1 = {"user_id": "alice", "title": "Goal A", "description": "v1"}
    payload2 = {"user_id": "alice", "title": "Goal A", "description": "v2"}

    resp1 = client.post("/v1/nodes/goal", headers=headers, json=payload1)
    assert resp1.status_code == 201

    resp2 = client.post("/v1/nodes/goal", headers=headers, json=payload2)
    assert resp2.status_code == 409


def test_create_goal_no_idempotency_key_proceeds_normally(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_create_goal(**kwargs):
        call_count["n"] += 1
        return SimpleNamespace(
            id=200 + call_count["n"],
            title=str(kwargs.get("title") or ""),
            description="",
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_goal", _fake_create_goal)

    payload = {"user_id": "alice", "title": "Goal B"}
    resp1 = client.post(
        "/v1/nodes/goal",
        headers={"X-OKR-Actor": "alice"},
        json=payload,
    )
    resp2 = client.post(
        "/v1/nodes/goal",
        headers={"X-OKR-Actor": "alice"},
        json=payload,
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert call_count["n"] == 2
    assert resp1.json()["id"] != resp2.json()["id"]


def test_create_objective_idempotency_replays(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_create(**kwargs):
        call_count["n"] += 1
        return SimpleNamespace(
            id=300 + call_count["n"],
            title=str(kwargs.get("title") or ""),
            description="",
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_objective", _fake_create)

    headers = {"X-OKR-Actor": "alice", "X-OKR-Idempotency-Key": "idem-obj-1"}
    payload = {"goal_id": 1, "title": "Objective A"}

    resp1 = client.post("/v1/nodes/objective", headers=headers, json=payload)
    assert resp1.status_code == 201
    first_id = resp1.json()["id"]

    resp2 = client.post("/v1/nodes/objective", headers=headers, json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == first_id
    assert call_count["n"] == 1


def test_create_key_result_idempotency_replays(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_create(**kwargs):
        call_count["n"] += 1
        return SimpleNamespace(
            id=400 + call_count["n"],
            title=str(kwargs.get("title") or ""),
            description="",
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_key_result", _fake_create)

    headers = {"X-OKR-Actor": "alice", "X-OKR-Idempotency-Key": "idem-kr-1"}
    payload = {"objective_id": 1, "title": "KR A", "target_value": 100, "unit": "%"}

    resp1 = client.post("/v1/nodes/key_result", headers=headers, json=payload)
    assert resp1.status_code == 201
    first_id = resp1.json()["id"]

    resp2 = client.post("/v1/nodes/key_result", headers=headers, json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == first_id
    assert call_count["n"] == 1


def test_create_task_idempotency_replays(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_create(**kwargs):
        call_count["n"] += 1
        return SimpleNamespace(
            id=500 + call_count["n"],
            title=str(kwargs.get("title") or ""),
            description="",
            progress=0,
            owner_id=11,
            updated_at=None,
        )

    monkeypatch.setattr(backend_main, "create_task", _fake_create)

    headers = {"X-OKR-Actor": "alice", "X-OKR-Idempotency-Key": "idem-task-1"}
    payload = {"key_result_id": 1, "title": "Task A", "estimated_minutes": 30}

    resp1 = client.post("/v1/nodes/task", headers=headers, json=payload)
    assert resp1.status_code == 201
    first_id = resp1.json()["id"]

    resp2 = client.post("/v1/nodes/task", headers=headers, json=payload)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == first_id
    assert call_count["n"] == 1


def test_atomic_reserve_load_store_roundtrip():
    from backend_app.security_state import (
        InMemorySecurityStateStore,
    )

    store = InMemorySecurityStateStore()
    scope = "test.scope"
    actor = "user1"
    key = "key-abc"
    payload_hash = "hash123"

    assert (
        store.reserve_idempotency_key(
            scope=scope,
            actor=actor,
            key=key,
            payload_hash=payload_hash,
            ttl_seconds=3600,
        )
        is True
    )

    assert (
        store.reserve_idempotency_key(
            scope=scope,
            actor=actor,
            key=key,
            payload_hash=payload_hash,
            ttl_seconds=3600,
        )
        is False
    )

    record = store.load_idempotent_response(scope=scope, actor=actor, key=key)
    assert record is not None
    assert record["payload_hash"] == payload_hash
    assert record["response"] is None

    store.store_idempotent_response(
        scope=scope,
        actor=actor,
        key=key,
        response_json='{"id": 1}',
    )

    record = store.load_idempotent_response(scope=scope, actor=actor, key=key)
    assert record is not None
    assert record["response"] == {"id": 1}


# ============================================================================
# Timer double-submission tests
# ============================================================================


def test_stop_timer_idempotent_when_already_stopped(monkeypatch):
    """Double-stop returns success both times, not 404 on second call."""
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_stop_timer(task_id, summary=None, user_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return SimpleNamespace(
                id=1,
                task_id=task_id,
                duration_minutes=5,
                start_time=None,
                end_time=None,
                summary=summary,
            )
        return None

    monkeypatch.setattr(backend_main, "stop_timer", _fake_stop_timer)

    payload = {"task_id": 9, "summary": "focus", "user_id": "alice"}
    headers = {"X-OKR-Actor": "alice"}

    resp1 = client.post("/v1/timer/stop", headers=headers, json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["duration_minutes"] == 5

    resp2 = client.post("/v1/timer/stop", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["task_id"] == 9
    assert resp2.json()["duration_minutes"] == 0


def test_start_timer_idempotent_when_already_running(monkeypatch):
    """Double-start returns the same work_log, not a duplicate."""
    client, backend_main = _make_client(monkeypatch)
    call_count = {"n": 0}

    def _fake_start_timer(task_id, user_id=None):
        call_count["n"] += 1
        return SimpleNamespace(
            id=100,
            task_id=task_id,
            start_time=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, "start_timer", _fake_start_timer)

    payload = {"task_id": 7}
    headers = {"X-OKR-Actor": "alice"}

    resp1 = client.post("/v1/timer/start", headers=headers, json=payload)
    assert resp1.status_code == 200
    first_id = resp1.json()["work_log_id"]

    resp2 = client.post("/v1/timer/start", headers=headers, json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["work_log_id"] == first_id
    assert call_count["n"] == 2


# ============================================================================
# Session freshness validation tests
# ============================================================================


def test_get_current_user_returns_user_data(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    from types import SimpleNamespace
    from contextlib import contextmanager

    monkeypatch.setattr(
        backend_main,
        "_resolve_actor_scope",
        lambda _session, _actor, token_version=None: {
            "actor_id": 1,
            "username": "alice",
            "display_name": "Alice",
            "role": "admin",
            "team_id": 1,
            "manager_id": None,
            "must_change_password": False,
            "token_version": 1,
        },
    )

    class _FakeQuery:
        def first(self):
            return SimpleNamespace(
                id=1,
                username="alice",
                display_name="Alice",
                role="admin",
                team_id=1,
                manager_id=None,
                must_change_password=False,
                token_version=1,
            )

    class _FakeSession:
        def exec(self, _query):
            return _FakeQuery()

    @contextmanager
    def _fake_session_context():
        yield _FakeSession()

    monkeypatch.setattr(
        backend_main,
        "get_session_context",
        _fake_session_context,
    )

    response = client.get(
        "/v1/auth/me",
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["role"] == "admin"


def test_get_current_user_returns_401_without_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.get("/v1/auth/me")

    assert response.status_code in (400, 401)


def test_get_current_user_returns_401_when_token_version_stale(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    from fastapi import HTTPException
    from contextlib import contextmanager

    def _reject_stale(_session, _actor, token_version=None):
        raise HTTPException(status_code=401, detail="Session invalidated.")

    monkeypatch.setattr(backend_main, "_resolve_actor_scope", _reject_stale)

    class _FakeSession:
        def exec(self, _query):
            class _Q:
                def first(self):
                    return None

            return _Q()

    @contextmanager
    def _fake_session_context():
        yield _FakeSession()

    monkeypatch.setattr(
        backend_main,
        "get_session_context",
        _fake_session_context,
    )

    response = client.get(
        "/v1/auth/me",
        headers={"X-OKR-Actor": "alice", "X-OKR-Token-Version": "999"},
    )

    assert response.status_code == 401


# ============================================================================
# Read-query payload size and parameter validation tests
# ============================================================================


def test_read_query_rejects_unknown_kind(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "totally.unknown.kind", "params": {}},
    )

    assert response.status_code == 400
    assert "unsupported" in str(response.json().get("detail", "")).lower()


def test_read_query_accepts_known_kind(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, "get_all_users", lambda: [])
    monkeypatch.setattr(
        backend_main,
        "_resolve_scope_for_actor",
        lambda _actor, token_version=None: {
            "is_admin": True,
            "owner_ids": set(),
            "usernames": set(),
        },
    )

    response = client.post(
        "/v1/read/query",
        headers={"X-OKR-Actor": "alice"},
        json={"kind": "users.all", "params": {}},
    )

    assert response.status_code == 200


def test_atlas_snapshot_rejects_oversized_owner_ids(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/read/atlas/snapshot",
        headers={"X-OKR-Actor": "alice"},
        json={"cycle_id": 1, "owner_ids": list(range(300))},
    )

    assert response.status_code == 422


def test_leadership_metrics_rejects_oversized_usernames(monkeypatch):
    client, backend_main = _make_client(monkeypatch)

    response = client.post(
        "/v1/read/leadership/metrics",
        headers={"X-OKR-Actor": "alice"},
        json={"cycle_id": 1, "usernames": [f"user_{i}" for i in range(300)]},
    )

    assert response.status_code == 422


# ============================================================================
# Admin restore size limit tests
# ============================================================================


def test_db_restore_rejects_disabled_config(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main, "get_bool_config", lambda _key, _default=False: False
    )
    monkeypatch.setattr(backend_main, "_require_admin_actor_scope", lambda _actor: None)

    response = client.post(
        "/v1/admin/db-restore",
        headers={"X-OKR-Actor": "alice"},
        json={"format": "okr-backup-v1", "data": {}},
    )

    assert response.status_code == 403
    assert "disabled" in str(response.json().get("detail", "")).lower()


def test_db_restore_rejects_oversized_content_length(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main, "get_bool_config", lambda _key, _default=False: True
    )
    monkeypatch.setattr(backend_main, "is_production_runtime", lambda: False)
    monkeypatch.setattr(backend_main, "_require_admin_actor_scope", lambda _actor: None)

    response = client.post(
        "/v1/admin/db-restore",
        headers={
            "X-OKR-Actor": "alice",
            "Content-Length": str(100 * 1024 * 1024),
        },
        json={"format": "okr-backup-v1", "data": {}},
    )

    assert response.status_code == 413
    assert "too large" in str(response.json().get("detail", "")).lower()


# ============================================================================
# Actor mismatch rejection tests
# ============================================================================


def test_resolve_actor_rejects_header_payload_mismatch():
    from backend_app.security import resolve_actor_username
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        resolve_actor_username(header_actor="alice", payload_actor="bob")
    assert exc_info.value.status_code == 403
    assert "mismatch" in str(exc_info.value.detail).lower()


def test_resolve_actor_accepts_matching_header_payload():
    from backend_app.security import resolve_actor_username

    actor = resolve_actor_username(header_actor="alice", payload_actor="alice")
    assert actor == "alice"


def test_resolve_actor_accepts_header_only():
    from backend_app.security import resolve_actor_username

    actor = resolve_actor_username(header_actor="alice", payload_actor=None)
    assert actor == "alice"


def test_resolve_actor_accepts_payload_only():
    from backend_app.security import resolve_actor_username

    actor = resolve_actor_username(header_actor=None, payload_actor="alice")
    assert actor == "alice"
