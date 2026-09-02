from __future__ import annotations

from scripts import slo_probe


class _FakeResponse:
    def __init__(self, headers=None, status=200, body=b"{}"):
        self.headers = headers or {}
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def test_server_timing_parser_ignores_unsafe_or_malformed_values() -> None:
    assert slo_probe._parse_server_timing(
        "data;dur=120.5, app;dur=3, bff-upstream;dur=125.5"
    ) == {"data": 120.5, "app": 3.0, "bff-upstream": 125.5}
    assert slo_probe._parse_server_timing("password=secret, data;dur=nope") == {}


def test_read_probe_reports_server_timing_attribution(monkeypatch) -> None:
    timings = [
        {"data": 120.0, "app": 5.0, "bff-upstream": 125.0},
        {"data": 140.0, "app": 7.0, "bff-upstream": 147.0},
    ]

    def fake_post(base, path, payload, cookie, **kwargs):
        sink = kwargs["timing_sink"]
        sink.append(timings[len(sink) % len(timings)])
        return 200, {}, 0.15

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    result = slo_probe._probe_read_p95(
        "http://probe", "session=1", {"user_id": 7, "cycle_id": 3}
    )

    assert "data_p50_ms=130.0" in result[0]["detail"]
    assert "bff-upstream_p50_ms=136.0" in result[0]["detail"]
    assert result[0]["attribution_ms"] == {
        "app": 6.0,
        "bff-upstream": 136.0,
        "data": 130.0,
    }


def test_snapshot_probe_uses_required_context_and_window(monkeypatch) -> None:
    calls = []

    def fake_post(base, path, payload, cookie, **kwargs):
        calls.append((path, payload, kwargs))
        return 200, {}, 0.01

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    result = slo_probe._probe_snapshot_latency(
        "http://probe", "session=1", {"user_id": 7, "cycle_id": 3}
    )

    assert result[0]["detail"] == "6/6 succeeded"
    payload = calls[0][1]
    assert payload["kind"] == "ritual.snapshot"
    assert payload["params"]["cycle_id"] == 3
    assert payload["params"]["window_start"] < payload["params"]["window_end"]
    assert payload["params"]["user_id"] == 7
    assert payload["actor_username"] == ""


def test_read_probe_uses_active_cycle_context(monkeypatch) -> None:
    calls = []

    def fake_post(base, path, payload, cookie, **kwargs):
        calls.append((path, payload, kwargs))
        return 200, {}, 0.01

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    result = slo_probe._probe_read_p95(
        "http://probe", "session=1", {"user_id": 7, "cycle_id": 3}
    )

    assert result[0]["detail"] == "10/10 succeeded"
    payload = calls[0][1]
    assert payload["kind"] == "krs.by_cycle"
    assert payload["params"]["cycle_id"] == 3
    assert payload["actor_username"] == ""


def test_weekly_plan_probe_is_valid_and_reuses_same_week(monkeypatch) -> None:
    payloads = []

    def fake_post(base, path, payload, cookie, **kwargs):
        payloads.append(payload)
        return 201, {}, 0.01

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    result = slo_probe._probe_mutation_error_rate(
        "http://probe", "session=1", {"user_id": 7, "cycle_id": 3}
    )

    assert result[0]["detail"] == "0/10 errored (weekly-plans upsert)"
    assert len({(p["user_id"], p["start_date"], p["end_date"]) for p in payloads}) == 1
    assert payloads[0]["p1"]
    assert set(payloads[0]) == {
        "user_id", "start_date", "end_date", "p1", "p2", "p3", "actor_username"
    }


def test_actor_context_keeps_user_when_no_active_cycle(monkeypatch) -> None:
    responses = {
        "users.by_username": (200, {"user": {"id": 7, "username": "probe"}}, 0.01),
        "cycles.active": (200, {"cycles": []}, 0.01),
    }

    def fake_post(_base, _path, payload, _cookie, **kwargs):
        return responses[payload["kind"]]

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)

    assert slo_probe._probe_actor_context(
        "http://probe", "session=1", "probe", "csrf"
    ) == {"user_id": 7, "cycle_id": 0}


def test_snapshot_context_requires_an_active_cycle_without_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(
        slo_probe,
        "_probe_actor_context",
        lambda *args, **kwargs: {"user_id": 7, "cycle_id": 0},
    )

    assert slo_probe._snapshot_context(
        "http://probe", "session=1", "probe", "csrf"
    ) == (None, None)


def test_snapshot_context_creates_only_explicit_disposable_cycle(monkeypatch) -> None:
    calls = []

    def fake_post(base, path, payload, cookie, **kwargs):
        calls.append(("POST", path, payload, kwargs))
        if payload.get("kind") == "users.by_username":
            return 200, {"user": {"id": 7, "role": "admin"}}, 0.01
        if payload.get("kind") == "cycles.all":
            return 200, {"cycles": []}, 0.01
        return 201, {
            "id": 91,
            "title": payload["title"],
            "is_active": True,
            "owner_manager_id": 7,
        }, 0.01

    def fake_delete(base, path, cookie, **kwargs):
        calls.append(("DELETE", path, kwargs))
        return 200, {"id": 91, "deleted": True}, 0.01

    monkeypatch.setattr(
        slo_probe,
        "_probe_actor_context",
        lambda *args, **kwargs: {"user_id": 7, "cycle_id": 0},
    )
    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    monkeypatch.setattr(slo_probe, "_delete_authenticated", fake_delete)

    context, cleanup = slo_probe._snapshot_context(
        "http://probe", "session=1", "probe", "csrf", allow_create=True
    )

    assert context == {"user_id": 7, "cycle_id": 91}
    assert cleanup == 91
    assert calls[2][1] == "/api/backend/v1/cycles"
    assert calls[2][2]["owner_manager_id"] == 7
    assert calls[2][2]["is_active"] is True


def test_snapshot_context_refuses_create_when_any_active_cycle_is_visible(monkeypatch) -> None:
    def fake_post(_base, _path, payload, _cookie, **kwargs):
        if payload.get("kind") == "users.by_username":
            return 200, {"user": {"id": 7, "role": "admin"}}, 0.01
        if payload.get("kind") == "cycles.all":
            return 200, {"cycles": [{"id": 44, "is_active": True}]}, 0.01
        raise AssertionError("must not create a cycle when an active cycle exists")

    monkeypatch.setattr(
        slo_probe,
        "_probe_actor_context",
        lambda *args, **kwargs: {"user_id": 7, "cycle_id": 0},
    )
    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)

    assert slo_probe._snapshot_context(
        "http://probe", "session=1", "probe", "csrf", allow_create=True
    ) == (None, None)


def test_snapshot_context_refuses_disposable_create_for_non_admin_probe(monkeypatch) -> None:
    def fake_post(_base, _path, payload, _cookie, **kwargs):
        if payload.get("kind") == "users.by_username":
            return 200, {"user": {"id": 7, "role": "member"}}, 0.01
        raise AssertionError("non-admin probes must not inspect or create cycles")

    monkeypatch.setattr(
        slo_probe,
        "_probe_actor_context",
        lambda *args, **kwargs: {"user_id": 7, "cycle_id": 0},
    )
    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)

    assert slo_probe._snapshot_context(
        "http://probe", "session=1", "probe", "csrf", allow_create=True
    ) == (None, None)


def test_snapshot_fixture_cleanup_deletes_only_created_cycle(monkeypatch) -> None:
    captured = {}

    def fake_delete(base, path, cookie, **kwargs):
        captured.update(path=path, cookie=cookie, csrf=kwargs.get("csrf_token"))
        return 200, {"deleted": True}, 0.01

    monkeypatch.setattr(slo_probe, "_delete_authenticated", fake_delete)
    assert slo_probe._cleanup_snapshot_cycle(
        "http://probe", "session=1", 91, "csrf"
    ) is True
    assert captured == {
        "path": "/api/backend/v1/cycles/91",
        "cookie": "session=1",
        "csrf": "csrf",
    }


def test_job_probe_uses_non_accumulating_pdf_job(monkeypatch) -> None:
    calls = []

    def fake_post(base, path, payload, cookie, **kwargs):
        calls.append((path, payload, kwargs))
        return 202, {"id": "job-1"}, 0.01

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    monkeypatch.setattr(
        slo_probe,
        "_get_json",
        lambda *args, **kwargs: (200, {"status": "succeeded"}, 0.01),
    )
    result = slo_probe._probe_job_queue_lag("http://probe", "session=1")

    assert result[0]["pass"]
    assert calls[0][1]["kind"] == "pdf.weekly"
    assert calls[0][2]["idempotency_key"] == "slo-probe-weekly-pdf"


def test_login_session_returns_csrf_token_for_mutations(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeResponse(
            headers={
                "Set-Cookie": (
                    "okr_spa_session=session-1; Path=/, "
                    "okr_csrf_token=csrf-1; Path=/"
                )
            }
        )

    monkeypatch.setattr(slo_probe.urllib.request, "urlopen", fake_urlopen)

    session_cookie, csrf_token = slo_probe._login_session(
        "http://probe", "member", "password"
    )

    assert session_cookie == "okr_spa_session=session-1; okr_csrf_token=csrf-1"
    assert csrf_token == "csrf-1"


def test_authenticated_post_sends_csrf_header(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(slo_probe.urllib.request, "urlopen", fake_urlopen)

    slo_probe._post_authenticated(
        "http://probe",
        "/api/backend/v1/jobs",
        {"kind": "pdf.weekly", "payload": {}},
        "okr_spa_session=session-1",
        csrf_token="csrf-1",
    )

    assert captured["request"].headers["X-xsrf-token"] == "csrf-1"


def test_job_probe_polls_string_job_id(monkeypatch) -> None:
    calls = []

    def fake_post(base, path, payload, cookie, **kwargs):
        calls.append((path, payload, kwargs))
        return 202, {"id": "job-uuid-1"}, 0.01

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return 200, {"status": "succeeded"}, 0.01

    monkeypatch.setattr(slo_probe, "_post_authenticated", fake_post)
    monkeypatch.setattr(slo_probe, "_get_json", fake_get)

    result = slo_probe._probe_job_queue_lag("http://probe", "session=1")

    assert result[0]["pass"]
    assert calls[1][0] == "http://probe/api/backend/v1/jobs/job-uuid-1"


def test_job_probe_skips_intentionally_unsupported_supabase_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        slo_probe,
        "_post_authenticated",
        lambda *args, **kwargs: (503, {}, 0.01),
    )

    result = slo_probe._probe_job_queue_lag(
        "http://probe",
        "session=1",
        data_access_mode="supabase_api",
    )

    assert result[0]["pass"] is True
    assert "intentionally unavailable" in result[0]["detail"]
