from types import SimpleNamespace


def test_timer_service_uses_backend_when_enabled(monkeypatch):
    import src.services.timer_service as timer_service

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")

    monkeypatch.setattr(
        timer_service,
        "backend_start_timer",
        lambda task_id, actor_username: {
            "work_log_id": 10,
            "task_id": task_id,
            "start_time": "2026-01-01T00:00:00",
        },
    )
    monkeypatch.setattr(
        timer_service,
        "backend_stop_timer",
        lambda task_id, actor_username, summary=None: {
            "work_log_id": 10,
            "task_id": task_id,
            "duration_minutes": 25,
            "summary": summary,
        },
    )

    started = timer_service.start_timer(99, "alice")
    assert isinstance(started, SimpleNamespace)
    assert started.task_id == 99

    stopped = timer_service.stop_timer(99, summary="focus", user_id="alice")
    assert isinstance(stopped, SimpleNamespace)
    assert int(stopped.duration_minutes) == 25


def test_timer_service_backend_404_maps_to_none(monkeypatch):
    import src.services.timer_service as timer_service

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setattr(
        timer_service,
        "backend_stop_timer",
        lambda task_id, actor_username, summary=None: {
            "error": "No active timer found.",
            "status_code": 404,
        },
    )

    assert timer_service.stop_timer(7, summary="x", user_id="alice") is None


def test_timer_service_falls_back_to_local_on_backend_transport_error(monkeypatch):
    import src.services.timer_service as timer_service
    import src.crud as crud

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_ALLOW_LOCAL_MUTATION_FALLBACK", "true")
    monkeypatch.setattr(
        timer_service,
        "backend_start_timer",
        lambda task_id, actor_username: {"error": "connection reset", "status_code": 0},
    )
    monkeypatch.setattr(
        timer_service,
        "backend_stop_timer",
        lambda task_id, actor_username, summary=None: {"error": "timeout", "status_code": 503},
    )
    monkeypatch.setattr(
        crud,
        "start_timer",
        lambda task_id, user_id: SimpleNamespace(task_id=task_id, start_time="t0"),
    )
    monkeypatch.setattr(
        crud,
        "stop_timer",
        lambda task_id, summary=None, user_id=None: SimpleNamespace(
            task_id=task_id,
            duration_minutes=10,
            summary=summary,
        ),
    )

    started = timer_service.start_timer(3, "alice")
    assert isinstance(started, SimpleNamespace)
    assert started.task_id == 3

    stopped = timer_service.stop_timer(3, summary="local", user_id="alice")
    assert isinstance(stopped, SimpleNamespace)
    assert int(stopped.duration_minutes) == 10


def test_timer_service_transient_backend_error_fails_closed_by_default(monkeypatch):
    import src.services.timer_service as timer_service

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.delenv("OKR_ALLOW_LOCAL_MUTATION_FALLBACK", raising=False)
    monkeypatch.delenv("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", raising=False)
    monkeypatch.setattr(
        timer_service,
        "backend_start_timer",
        lambda task_id, actor_username: {"error": "connection reset", "status_code": 0},
    )

    try:
        timer_service.start_timer(9, "alice")
        assert False, "Expected ValueError when fallback is disabled."
    except ValueError as exc:
        assert "fallback is disabled" in str(exc).lower()
