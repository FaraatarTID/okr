from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient


def _make_client(monkeypatch):
    import backend_app.main as backend_main

    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "false")
    monkeypatch.setattr(backend_main, "init_database", lambda: None)
    return TestClient(backend_main.app), backend_main


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
    assert str(getattr(captured.get("role"), "value", captured.get("role"))) == "manager"
    assert int(captured.get("team_id")) == 7
    assert response.json()["role"] == "manager"


def test_create_user_endpoint_rejects_weak_password_when_strict_policy_enabled(monkeypatch):
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
