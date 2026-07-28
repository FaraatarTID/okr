from types import SimpleNamespace
from fastapi.routing import APIRoute
import re

from fastapi.testclient import TestClient
import pytest
from pathlib import Path

import backend_app.main as backend_main
from backend_app.main import BACKUP_FORMAT_VERSION


def _make_client(monkeypatch):
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_SECURITY_STATE_BACKEND", "memory")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_WINDOW_SECONDS", "3600")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


def _fixture_password(name: str) -> str:
    return f"{name}-unit-test-password"


def _deny_forbidden(*_args, **_kwargs):
    raise PermissionError("Actor is not authorized.")


def _set_member_scope(monkeypatch, backend_main_obj):
    monkeypatch.setattr(
        backend_main_obj,
        "_resolve_scope_for_actor",
        lambda *args, **kwargs: {
            "is_admin": False,
            "role": "member",
            "owner_ids": set(),
            "usernames": {"member"},
            "manager_id": None,
        },
    )


_MUTATION_AUTH_MATRIX_ROUTES = [
    (
        "POST",
        "/v1/cycles",
        {"title": "Q1", "start_date": "2026-01-01", "end_date": "2026-03-31"},
        ("create_cycle",),
    ),
    (
        "PATCH",
        "/v1/cycles/11",
        {
            "title": "Q1",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "is_active": True,
        },
        ("update_cycle",),
    ),
    ("DELETE", "/v1/cycles/11", None, ("delete_cycle",)),
    (
        "POST",
        "/v1/teams",
        {"name": "Team Alpha", "description": "Security matrix"},
        ("create_team",),
    ),
    (
        "PATCH",
        "/v1/teams/11",
        {"name": "Team Renamed", "description": "Updated"},
        ("update_team",),
    ),
    ("DELETE", "/v1/teams/11", None, ("delete_team",)),
    (
        "PATCH",
        "/v1/users/11",
        {"display_name": "Blocked User"},
        ("update_user",),
    ),
    (
        "POST",
        "/v1/users",
        {
            "username": "newmember",
            "password": _fixture_password("newmember"),
            "role": "member",
        },
        ("create_user",),
    ),
    (
        "POST",
        "/v1/users/11/reset-password",
        {"new_password": _fixture_password("reset")},
        ("reset_user_password",),
    ),
    (
        "POST",
        "/v1/check-ins",
        {
            "kr_id": 1,
            "value": 22,
            "confidence": 9,
            "variation_type": "COMMON_CAUSE",
        },
        ("create_check_in",),
    ),
    (
        "POST",
        "/v1/experiments",
        {
            "key_result_id": 1,
            "cycle_id": 1,
            "hypothesis": "A controlled experiment",
            "change_description": "Testing scope boundaries",
        },
        ("create_experiment",),
    ),
    (
        "PATCH",
        "/v1/experiments/11",
        {},
        ("update_experiment",),
    ),
    (
        "POST",
        "/v1/experiments/11/close",
        {"decision": "ADOPT", "rationale": "Test close"},
        ("close_experiment",),
    ),
    (
        "POST",
        "/v1/retrospectives",
        {
            "user_id": 1,
            "cycle_id": 11,
            "week_start_date": "2026-01-01",
            "content": "Member scope regression",
        },
        ("create_retrospective",),
    ),
    (
        "PUT",
        "/v1/retrospectives/11/experiment-outcomes",
        {"experiment_id": 1, "decision": "ADOPT", "rationale": "Blocked outcome"},
        ("upsert_retro_experiment_outcome",),
    ),
    (
        "POST",
        "/v1/weekly-plans",
        {
            "user_id": 1,
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
            "p1": "Focus",
        },
        ("create_weekly_plan",),
    ),
    (
        "POST",
        "/v1/alignments",
        {"parent_id": 1, "child_id": 2},
        ("create_alignment",),
    ),
    ("DELETE", "/v1/alignments/11", None, ("delete_alignment",)),
    (
        "POST",
        "/v1/objective-alignment-links",
        {
            "objective_id": 1,
            "linked_entity_type": "goal",
            "linked_entity_id": 2,
            "direction": "parent",
        },
        ("create_objective_alignment_link",),
    ),
    (
        "DELETE",
        "/v1/objective-alignment-links/11",
        None,
        ("delete_objective_alignment_link",),
    ),
    ("DELETE", "/v1/work-logs/11", None, ("delete_work_log",)),
    (
        "POST",
        "/v1/nodes/goal",
        {"user_id": "member"},
        ("create_goal",),
    ),
    (
        "POST",
        "/v1/nodes/objective",
        {"goal_id": 1},
        ("create_objective",),
    ),
    (
        "POST",
        "/v1/nodes/key_result",
        {"objective_id": 1},
        ("create_key_result",),
    ),
    ("POST", "/v1/nodes/task", {"key_result_id": 1}, ("create_task",)),
    (
        "PATCH",
        "/v1/nodes/goal/11",
        {"updates": {"title": "Goal edit"}, "actor_username": "member"},
        ("update_goal",),
    ),
    (
        "PATCH",
        "/v1/nodes/objective/11",
        {"updates": {"title": "Objective edit"}, "actor_username": "member"},
        ("update_objective",),
    ),
    (
        "PATCH",
        "/v1/nodes/key_result/11",
        {"updates": {"title": "KR edit"}, "actor_username": "member"},
        ("update_key_result",),
    ),
    (
        "PATCH",
        "/v1/nodes/task/11",
        {"updates": {"title": "Task edit"}, "actor_username": "member"},
        ("update_task",),
    ),
    ("DELETE", "/v1/nodes/goal/11", None, ("delete_goal",)),
    ("DELETE", "/v1/nodes/objective/11", None, ("delete_objective",)),
    ("DELETE", "/v1/nodes/key_result/11", None, ("delete_key_result",)),
    ("DELETE", "/v1/nodes/task/11", None, ("delete_task",)),
]

_MUTATION_ROUTE_ALLOWLIST = {
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/read/query"),
    ("POST", "/v1/read/atlas/snapshot"),
    ("POST", "/v1/read/leadership/metrics"),
    ("POST", "/v1/admin/db-restore"),
    ("POST", "/v1/ai/analyze-node"),
    ("POST", "/v1/ai/team-coach"),
    ("POST", "/v1/ai/strategy-pulse"),
    ("POST", "/v1/jobs"),
    ("POST", "/v1/jobs/{job_id}/cancel"),
    ("DELETE", "/v1/jobs/{job_id}"),
    ("POST", "/v1/timer/start"),
    ("POST", "/v1/timer/stop"),
    ("POST", "/v1/users/{user_id}/reset-password"),
    ("PUT", "/v1/retrospectives/{retrospective_id}/experiment-outcomes"),
    ("POST", "/v1/read/atlas/snapshot"),
    ("POST", "/v1/state/{key}"),
    ("DELETE", "/v1/nodes/{node_type}/{node_id}"),
    ("PATCH", "/v1/nodes/{node_type}/{node_id}"),
}

_MUTATION_MATRIX_ROUTE_SET = {
    (method, path) for method, path, _, __ in _MUTATION_AUTH_MATRIX_ROUTES
}

_ROUTE_PARAM_NORMALIZER = re.compile(r"{[^}]+}")
_NUMERIC_SEGMENT = re.compile(r"/\d+")
_ALLOWLIST_PATH_WITH_TYPE_RE = re.compile(r"{[^{}:]+:int}")
_ALLOWLIST_PATH_PARAM_RE = re.compile(r"{[^{}]+}")


def _normalize_mutation_route(
    route: tuple[str, str] | tuple[str, str],
) -> tuple[str, str]:
    method, path = route
    if path.startswith("/api/"):
        path = path.removeprefix("/api")
    segments = path.split("/")
    if len(segments) >= 4 and segments[1] == "v1" and segments[2] == "nodes":
        if len(segments) >= 5:
            if (
                not (segments[3].startswith("{") and segments[3].endswith("}"))
                and not segments[3].isdigit()
            ):
                segments[3] = "{param}"
            if not (
                segments[4].startswith("{")
                and segments[4].endswith("}")
                or segments[4].isdigit()
            ):
                segments[4] = "{param}"
        elif segments[3] and (
            not (segments[3].startswith("{") and segments[3].endswith("}"))
            and not segments[3].isdigit()
        ):
            segments[3] = "{param}"
        path = "/".join(segments)

    normalized_path = _ROUTE_PARAM_NORMALIZER.sub("{param}", path)
    normalized_path = _NUMERIC_SEGMENT.sub("/{param}", normalized_path)
    return method, normalized_path


def _normalize_allowlist_path(path_template: str) -> str:
    normalized = _ALLOWLIST_PATH_WITH_TYPE_RE.sub("{param}", path_template)
    normalized = _ALLOWLIST_PATH_PARAM_RE.sub("{param}", normalized)
    return normalized


def _allowlist_mutation_routes() -> set[tuple[str, str]]:
    project_root = Path(__file__).resolve().parents[1]
    allowlist_file = project_root / "spa-bff" / "src" / "allowlist.ts"
    allowlist_text = allowlist_file.read_text(encoding="utf-8")

    entry_re = re.compile(
        r"\{\s*pathTemplate:\s*\"([^\"]+)\"\s*,\s*methods:\s*\[([^\]]+)\]",
        re.MULTILINE,
    )
    routes: set[tuple[str, str]] = set()
    for path_template, method_blob in entry_re.findall(allowlist_text):
        methods = re.findall(r"\"(GET|POST|PUT|PATCH|DELETE)\"", method_blob)
        for method in methods:
            if method not in {"POST", "PUT", "PATCH", "DELETE"}:
                continue
            normalized_path = path_template
            if normalized_path.startswith("/api/"):
                normalized_path = normalized_path.removeprefix("/api")
            routes.add((method, _normalize_allowlist_path(normalized_path)))
    return routes


def _render_route(method: str, path: str) -> str:
    return f"{method} {path}"


def _mutating_v1_routes_from_app() -> set[tuple[str, str]]:
    import backend_app.main as backend_main

    def _iter_api_routes(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                yield route
                continue
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                yield from _iter_api_routes(getattr(original_router, "routes", []))

    mutation_routes = set()
    for route in _iter_api_routes(backend_main.app.routes):
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or ():
            if method in {"POST", "PUT", "PATCH", "DELETE"} and (
                route.path.startswith("/v1/") or route.path.startswith("/api/v1/")
            ):
                mutation_routes.add((method, route.path))
    return mutation_routes


def test_mutation_route_matrix_covers_all_v1_mutation_routes():
    app_routes = {
        _normalize_mutation_route(route) for route in _mutating_v1_routes_from_app()
    }
    matrix_routes_raw = {
        _normalize_mutation_route(route) for route in _MUTATION_MATRIX_ROUTE_SET
    }
    matrix_routes = matrix_routes_raw.intersection(app_routes)
    allowed_routes = {
        _normalize_mutation_route(route) for route in _MUTATION_ROUTE_ALLOWLIST
    }
    covered_routes = matrix_routes | allowed_routes

    missing_from_matrix = sorted(app_routes - covered_routes)
    assert not missing_from_matrix, "Mutation route(s) missing coverage: " + ", ".join(
        _render_route(*route) for route in missing_from_matrix
    )

    matrix_only_routes = sorted(matrix_routes - app_routes)
    assert not matrix_only_routes, "Matrix contains stale route(s): " + ", ".join(
        _render_route(*route) for route in matrix_only_routes
    )


def test_mutation_routes_are_in_bff_allowlist():
    app_routes = {
        _normalize_mutation_route(route) for route in _mutating_v1_routes_from_app()
    }
    allowlist_routes = _allowlist_mutation_routes() & app_routes

    missing_from_allowlist = sorted(app_routes - allowlist_routes)
    assert not missing_from_allowlist, (
        "Mutation routes missing from BFF allowlist: "
        + ", ".join(_render_route(*route) for route in missing_from_allowlist)
    )

    stale_allowlist_entries = sorted(allowlist_routes - app_routes)
    assert not stale_allowlist_entries, (
        "BFF allowlist has stale mutation routes: "
        + ", ".join(_render_route(*route) for route in stale_allowlist_entries)
    )


@pytest.mark.parametrize(
    "method,path,payload,service_fns",
    _MUTATION_AUTH_MATRIX_ROUTES,
)
def test_mutation_endpoints_reject_non_admin_member(
    monkeypatch, method, path, payload, service_fns
):
    client, backend_main_obj = _make_client(monkeypatch)
    _set_member_scope(monkeypatch, backend_main_obj)
    for service_fn in service_fns:
        monkeypatch.setattr(backend_main_obj, service_fn, _deny_forbidden)

    response = client.request(
        method, path, headers={"X-OKR-Actor": "member"}, json=payload
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "path,payload",
    [
        (
            "/v1/ai/analyze-node",
            {"node_id": 11, "node_type": "TASK", "actor_username": "mallory"},
        ),
        ("/v1/ai/team-coach", {"actor_username": "mallory", "team_data": {}}),
        (
            "/v1/ai/strategy-pulse",
            {
                "actor_username": "mallory",
                "cycle_id": 11,
                "subject_username": "member",
                "cycle_title": "Scope test",
            },
        ),
    ],
)
def test_ai_endpoints_reject_actor_payload_mismatch(monkeypatch, path, payload):
    client, _ = _make_client(monkeypatch)

    response = client.post(path, headers={"X-OKR-Actor": "member"}, json=payload)
    assert response.status_code == 403


def test_jobs_submit_rejects_actor_payload_mismatch(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.post(
        "/v1/jobs",
        headers={"X-OKR-Actor": "member"},
        json={
            "kind": "ai.generate_json",
            "payload": {"prompt": "hello"},
            "actor_username": "mallory",
        },
    )
    assert response.status_code == 403


def test_jobs_cancel_rejects_non_owner_member(monkeypatch):
    client, backend_main_obj = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main_obj, "request_job_cancel", lambda *_args, **_kwargs: None
    )

    response = client.post(
        "/v1/jobs/11/cancel",
        headers={"X-OKR-Actor": "member"},
    )
    assert response.status_code == 404
    assert "not found" in str(response.json().get("detail", "")).lower()


def test_jobs_delete_rejects_non_owner_member(monkeypatch):
    client, backend_main_obj = _make_client(monkeypatch)
    monkeypatch.setattr(
        backend_main_obj,
        "get_job",
        lambda *_args, **_kwargs: SimpleNamespace(actor_username="someone_else"),
    )

    response = client.delete(
        "/v1/jobs/11",
        headers={"X-OKR-Actor": "member"},
    )
    assert response.status_code == 404
    assert "not found" in str(response.json().get("detail", "")).lower()


def test_timer_start_rejects_actor_payload_mismatch(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.post(
        "/v1/timer/start",
        headers={"X-OKR-Actor": "member"},
        json={"task_id": 11, "user_id": "alice"},
    )
    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_timer_stop_rejects_actor_payload_mismatch(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.post(
        "/v1/timer/stop",
        headers={"X-OKR-Actor": "member"},
        json={"task_id": 11, "user_id": "alice"},
    )
    assert response.status_code == 403
    assert "mismatch" in str(response.json().get("detail", "")).lower()


def test_admin_db_restore_rejects_non_admin_member(monkeypatch):
    client, backend_main_obj = _make_client(monkeypatch)
    _set_member_scope(monkeypatch, backend_main_obj)

    response = client.post(
        "/v1/admin/db-restore",
        headers={"X-OKR-Actor": "member"},
        json={"format": BACKUP_FORMAT_VERSION, "data": {}},
    )
    assert response.status_code == 403


def test_app_state_set_rejects_non_admin_member(monkeypatch):
    client, backend_main_obj = _make_client(monkeypatch)
    _set_member_scope(monkeypatch, backend_main_obj)

    response = client.post(
        "/v1/state/runtime-mode",
        headers={"X-OKR-Actor": "member", "Content-Type": "application/json"},
        content='{"value":"disabled"}',
    )
    assert response.status_code == 403
