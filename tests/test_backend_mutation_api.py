from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


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


def test_update_node_endpoint_prefers_header_actor_over_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_update_task(task_id, actor_username=None, **updates):
        captured["task_id"] = task_id
        captured["actor_username"] = actor_username
        captured["updates"] = updates
        return SimpleNamespace(
            id=task_id,
            title="Task Updated",
            description="",
            progress=40,
            owner_id=7,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, "update_task", _fake_update_task)

    response = client.patch(
        "/v1/nodes/task/88",
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "updates": {"title": "Task Updated", "progress": 40},
        },
    )

    assert response.status_code == 200
    assert int(captured["task_id"]) == 88
    assert captured["actor_username"] == "alice"
    assert captured["updates"]["title"] == "Task Updated"


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


def test_create_task_endpoint_prefers_header_actor_over_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_create_task(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=91,
            title=str(kwargs.get("title") or ""),
            description=str(kwargs.get("description") or ""),
            progress=0,
            owner_id=kwargs.get("assignee_id"),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, "create_task", _fake_create_task)

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

    assert response.status_code == 201
    assert captured["actor_username"] == "alice"
    assert int(captured["key_result_id"]) == 3201


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
                "actor_username": "mallory",
            },
            "TASK",
        ),
    ],
)
def test_create_node_endpoints_prefer_header_actor_over_payload_actor(
    monkeypatch, route_path, create_fn, payload, node_type
):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id=401,
            title=str(kwargs.get("title") or ""),
            description=str(kwargs.get("description") or ""),
            progress=0,
            owner_id=7,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, create_fn, _fake_create)
    response = client.post(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json=payload,
    )

    assert response.status_code == 201
    assert captured["actor_username"] == "alice"
    assert response.json()["node_type"] == node_type


@pytest.mark.parametrize(
    ("route_path", "update_fn", "expected_type"),
    [
        ("/v1/nodes/goal/88", "update_goal", "GOAL"),
        ("/v1/nodes/objective/88", "update_objective", "OBJECTIVE"),
        ("/v1/nodes/key_result/88", "update_key_result", "KEY_RESULT"),
        ("/v1/nodes/task/88", "update_task", "TASK"),
    ],
)
def test_update_node_endpoints_prefer_header_actor_over_payload_actor_for_all_types(
    monkeypatch, route_path, update_fn, expected_type
):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_update(node_id, actor_username=None, **updates):
        captured["node_id"] = node_id
        captured["actor_username"] = actor_username
        captured["updates"] = updates
        return SimpleNamespace(
            id=node_id,
            title="Node Updated",
            description="",
            progress=40,
            owner_id=7,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, update_fn, _fake_update)
    response = client.patch(
        route_path,
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "updates": {"title": "Node Updated", "progress": 40},
        },
    )

    assert response.status_code == 200
    assert int(captured["node_id"]) == 88
    assert captured["actor_username"] == "alice"
    assert response.json()["node_type"] == expected_type


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
def test_delete_node_endpoint_returns_404_when_missing(monkeypatch, route_path, delete_fn):
    client, backend_main = _make_client(monkeypatch)
    monkeypatch.setattr(backend_main, delete_fn, lambda *_args, **_kwargs: False)

    response = client.delete(
        route_path,
        headers={"X-OKR-Actor": "alice"},
    )

    assert response.status_code == 404
    assert "not found" in str(response.json().get("detail", "")).lower()


def test_start_timer_endpoint_prefers_header_actor_over_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_start_timer(task_id, actor):
        captured["task_id"] = task_id
        captured["actor"] = actor
        return SimpleNamespace(
            id=11,
            task_id=task_id,
            start_time=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    monkeypatch.setattr(backend_main, "start_timer", _fake_start_timer)

    response = client.post(
        "/v1/timer/start",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 7, "user_id": "mallory"},
    )

    assert response.status_code == 200
    assert int(captured["task_id"]) == 7
    assert captured["actor"] == "alice"


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


def test_stop_timer_endpoint_prefers_header_actor_over_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_stop_timer(task_id, summary=None, user_id=None):
        captured["task_id"] = task_id
        captured["summary"] = summary
        captured["user_id"] = user_id
        return SimpleNamespace(
            id=12,
            task_id=task_id,
            duration_minutes=15,
            start_time=datetime.now(timezone.utc).replace(tzinfo=None),
            end_time=datetime.now(timezone.utc).replace(tzinfo=None),
            summary=summary,
        )

    monkeypatch.setattr(backend_main, "stop_timer", _fake_stop_timer)

    response = client.post(
        "/v1/timer/stop",
        headers={"X-OKR-Actor": "alice"},
        json={"task_id": 9, "summary": "focus", "user_id": "mallory"},
    )

    assert response.status_code == 200
    assert int(captured["task_id"]) == 9
    assert captured["summary"] == "focus"
    assert captured["user_id"] == "alice"


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

    assert response.status_code == 404
    assert "no active timer" in str(response.json().get("detail", "")).lower()


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
            "password": "secret123",
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

    response = client.post(
        "/v1/users",
        headers={"X-OKR-Actor": "admin"},
        json={
            "username": "member1",
            "password": "weakpass",
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
        lambda _session, _actor: {
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


def test_read_atlas_snapshot_prefers_header_actor_over_payload_actor(monkeypatch):
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
        lambda _session, actor: (
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
            "actor_username": "mallory",
        },
    )

    assert response.status_code == 200
    assert captured["resolved_actor"] == "alice"
    assert captured["cycle_id"] == 7
    assert captured["owner_ids"] == [1]


def test_read_atlas_snapshot_rejects_unauthorized_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    from contextlib import contextmanager

    @contextmanager
    def _fake_session_context():
        yield object()

    monkeypatch.setattr(backend_main, "get_session_context", _fake_session_context)

    def _deny_scope(_session, _actor):
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
        lambda _session, _actor: {
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
        lambda _session, _actor: {
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
        lambda _session, _actor: {
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
        lambda _actor: {"is_admin": True, "owner_ids": set(), "usernames": {"alice"}},
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
        lambda _actor: {"is_admin": True, "owner_ids": set(), "usernames": {"alice"}},
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

    monkeypatch.setattr(backend_main, "_serialize_key_result", _fake_serialize_key_result)

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


def test_ai_analyze_node_endpoint_prefers_header_actor_over_payload_actor(monkeypatch):
    client, backend_main = _make_client(monkeypatch)
    captured = {}

    def _fake_analyze_node(node_id, node_type="KEY_RESULT", actor_username=None):
        captured["node_id"] = node_id
        captured["node_type"] = node_type
        captured["actor_username"] = actor_username
        return {"overall_score": 84, "summary": "healthy"}

    monkeypatch.setattr(backend_main, "analyze_node", _fake_analyze_node)

    response = client.post(
        "/v1/ai/analyze-node",
        headers={"X-OKR-Actor": "alice"},
        json={
            "node_id": 42,
            "node_type": "OBJECTIVE",
            "actor_username": "mallory",
        },
    )

    assert response.status_code == 200
    assert int(captured["node_id"]) == 42
    assert str(captured["node_type"]) == "OBJECTIVE"
    assert captured["actor_username"] == "alice"
    assert int(response.json().get("overall_score", 0)) == 84


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
    monkeypatch.setattr(backend_main, "analyze_node", lambda *args, **kwargs: {"error": error_text})

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


def test_ai_team_coach_endpoint_prefers_header_actor_over_payload_actor(monkeypatch):
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
        lambda _session, actor: (
            captured.__setitem__("resolved_actor", actor)
            or {
                "is_admin": True,
                "owner_ids": {1},
                "usernames": {actor},
            }
        ),
    )

    def _fake_analyze_team_health(team_data):
        captured["team_data"] = team_data
        return {
            "coaching": {
                "top_priorities": ["Close check-in cadence gaps"],
            }
        }

    monkeypatch.setattr(backend_main, "analyze_team_health", _fake_analyze_team_health)

    response = client.post(
        "/v1/ai/team-coach",
        headers={"X-OKR-Actor": "alice"},
        json={
            "actor_username": "mallory",
            "team_data": {"total_krs": 9, "avg_confidence": 7.2},
        },
    )

    assert response.status_code == 200
    assert captured["resolved_actor"] == "alice"
    assert captured["team_data"] == {"total_krs": 9, "avg_confidence": 7.2}
    assert response.json().get("coaching", {}).get("top_priorities") == [
        "Close check-in cadence gaps"
    ]


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
        lambda _session, _actor: {"is_admin": False, "owner_ids": {1}, "usernames": {"alice"}},
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
        lambda _session, _actor: {"is_admin": False, "owner_ids": {1}, "usernames": {"alice"}},
    )
    monkeypatch.setattr(backend_main, "analyze_team_health", lambda *_args, **_kwargs: ["bad"])

    response = client.post(
        "/v1/ai/team-coach",
        headers={"X-OKR-Actor": "alice"},
        json={"team_data": {"total_krs": 4}},
    )

    assert response.status_code == 500
    assert "invalid payload" in str(response.json().get("detail", "")).lower()


def test_ai_strategy_pulse_endpoint_prefers_header_actor_and_returns_payload(monkeypatch):
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
        lambda _session, actor: (
            captured.__setitem__("resolved_actor", actor)
            or {
                "is_admin": False,
                "owner_ids": {1},
                "usernames": {"alice", "bob"},
            }
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "get_user_by_username",
        lambda username: (
            captured.__setitem__("subject_username", username)
            or SimpleNamespace(id=7, username=username)
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "calculate_burnout_risk",
        lambda user_id, days=14: (
            captured.__setitem__("burnout_args", {"user_id": user_id, "days": days})
            or {
                "risk_score": 62.0,
                "risk_label": "High",
                "avg_daily_minutes": 270.0,
                "completed_tasks": 11,
                "work_days": 8,
            }
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "detect_strategy_gaps",
        lambda cycle_id, user_ids=None: (
            captured.__setitem__("gaps_args", {"cycle_id": cycle_id, "user_ids": user_ids})
            or [{"title": "Objective A", "gap_type": "STALLED", "severity": 74, "progress": 22}]
        ),
    )
    monkeypatch.setattr(
        backend_main,
        "generate_predictive_outlook",
        lambda burnout_data, strategy_gaps, cycle_title="Current Cycle": (
            captured.__setitem__(
                "outlook_args",
                {
                    "burnout_data": burnout_data,
                    "strategy_gaps": strategy_gaps,
                    "cycle_title": cycle_title,
                },
            )
            or {
                "outlook_summary": "Execution risk is rising and requires focused triage.",
                "risk_mitigation": ["Trim low-impact scope this sprint."],
                "strategic_pivots": ["Shift effort to customer-critical KRs."],
                "confidence_level": 78,
            }
        ),
    )

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

    assert response.status_code == 200
    payload = response.json()
    assert captured["resolved_actor"] == "alice"
    assert captured["subject_username"] == "bob"
    assert captured["burnout_args"] == {"user_id": 7, "days": 21}
    assert captured["gaps_args"] == {"cycle_id": 9, "user_ids": [7]}
    assert captured["outlook_args"]["cycle_title"] == "Q1-2026"
    assert payload.get("burnout_risk") == "High"
    assert payload.get("subject_username") == "bob"
    assert isinstance(payload.get("gap_signals"), list)
    assert isinstance(payload.get("portfolio_actions"), list)


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
        lambda _session, _actor: {
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
        lambda _session, _actor: {
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
        lambda _session, _actor: {
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
    monkeypatch.setattr(backend_main, "detect_strategy_gaps", lambda *_args, **_kwargs: [])
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
        lambda _session, _actor: {
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
    monkeypatch.setattr(backend_main, "detect_strategy_gaps", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(backend_main, "generate_predictive_outlook", lambda *_args, **_kwargs: "invalid")

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
        lambda _actor: {
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
            SimpleNamespace(id=3, title="Q1", start_date=None, end_date=None, is_active=True),
            SimpleNamespace(id=8, title="Q2", start_date=None, end_date=None, is_active=True),
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
        lambda _session, _actor: {
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
            SimpleNamespace(id=5, title="Q-active", start_date=None, end_date=None, is_active=True),
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
