"""Local (in-process) behavior of the timer and job service wrappers."""

from __future__ import annotations

import src.crud as crud
from src.services import job_service, timer_service


def test_timer_service_start_delegates_to_crud(monkeypatch):
    calls = []
    monkeypatch.setattr(
        crud,
        "start_timer",
        lambda task_id, user_id: calls.append((task_id, user_id)) or "log",
    )

    assert timer_service.start_timer("7", 12) == "log"
    assert calls == [(7, "12")]


def test_timer_service_stop_delegates_to_crud(monkeypatch):
    calls = []

    def _stop(task_id, summary=None, user_id=None):
        calls.append((task_id, summary, user_id))
        return "stopped"

    monkeypatch.setattr(crud, "stop_timer", _stop)

    assert timer_service.stop_timer("7", summary="focus", user_id="alice") == "stopped"
    assert calls == [(7, "focus", "alice")]


def test_run_job_and_wait_runs_locally(monkeypatch):
    seen = []
    monkeypatch.setattr(
        job_service,
        "generate_json",
        lambda prompt: seen.append(prompt) or {"ok": True},
    )

    result = job_service.run_job_and_wait(
        kind="ai.generate_json",
        payload={"prompt": " hello "},
        actor_username="alice",
    )

    assert result == {"ok": True}
    assert seen == ["hello"]


def test_run_job_and_wait_reports_missing_prompt_and_unknown_kind():
    missing = job_service.run_job_and_wait(
        kind="ai.generate_json", payload={}, actor_username="alice"
    )
    assert missing == {"error": "Missing prompt."}

    unknown = job_service.run_job_and_wait(
        kind="nope", payload={}, actor_username="alice"
    )
    assert "Unsupported job kind" in unknown["error"]
