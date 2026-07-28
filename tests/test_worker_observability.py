from types import SimpleNamespace


import json

def test_worker_process_sets_job_observability_context(monkeypatch):
    import backend_app.worker as worker
    from src.observability import get_correlation_id, get_request_id

    observed = {}

    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="abc123",
            kind="ai.generate_json",
            payload_json='{"prompt":"hello"}',
        ),
    )
    monkeypatch.setattr(worker, "get_job", lambda _job_id: None)
    monkeypatch.setattr(worker, "mark_job_cancelled", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "mark_job_failed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        worker,
        "mark_job_succeeded",
        lambda job_id, result: observed.update({"job_id": job_id, "result": result}),
    )

    def _fake_run_job(kind, payload):
        observed["kind"] = kind
        observed["payload"] = payload
        observed["correlation_id"] = get_correlation_id()
        observed["request_id"] = get_request_id()
        return {"ok": True}

    monkeypatch.setattr(worker, "run_job", _fake_run_job)

    handled = worker.process_next_job(worker_id="worker-1")

    assert handled is True
    assert observed["kind"] == "ai.generate_json"
    assert observed["payload"] == {"prompt": "hello"}
    assert observed["correlation_id"] == "job-abc123"
    assert observed["request_id"] == "job-abc123"
    assert observed["job_id"] == "abc123"


def test_worker_process_logs_structured_events(monkeypatch):
    import backend_app.worker as worker

    logs: list[str] = []
    monkeypatch.setattr(worker.logger, "info", lambda payload: logs.append(str(payload)))
    monkeypatch.setattr(worker.logger, "warning", lambda payload: logs.append(str(payload)))
    monkeypatch.setattr(worker.logger, "debug", lambda payload: logs.append(str(payload)))
    monkeypatch.setattr(worker.logger, "exception", lambda payload: logs.append(str(payload)))

    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="logjob",
            kind="ai.generate_json",
            payload_json='{"prompt":"hello"}',
        ),
    )
    monkeypatch.setattr(worker, "get_job", lambda _job_id: None)
    monkeypatch.setattr(worker, "mark_job_cancelled", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "mark_job_failed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        worker,
        "mark_job_succeeded",
        lambda job_id, result: None,
    )

    def _fake_run_job(kind, payload):
        return {"ok": True}

    monkeypatch.setattr(worker, "run_job", _fake_run_job)

    handled = worker.process_next_job(worker_id="worker-1")
    assert handled is True

    payloads = [
        json.loads(item)
        for item in logs
        if item.strip().startswith("{") and item.strip().endswith("}")
    ]
    start_events = [entry for entry in payloads if entry.get("event") == "worker_job_started"]
    final_events = [entry for entry in payloads if entry.get("event") == "worker_job_finalized"]
    assert start_events
    assert final_events
    assert start_events[0]["job_id"] == "job-logjob"
    assert start_events[0]["worker_id"] == "worker-1"
    assert final_events[-1]["status"] in {"success", "cancelled"}


def test_worker_process_marks_malformed_payload_terminal(monkeypatch):
    import backend_app.worker as worker

    observed = {}

    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="bad1",
            kind="ai.generate_json",
            payload_json="{bad-json",
        ),
    )
    monkeypatch.setattr(worker, "run_job", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        worker,
        "mark_job_failed_terminal",
        lambda job_id, error_text: observed.update(
            {"job_id": job_id, "error_text": error_text}
        ),
    )
    monkeypatch.setattr(
        worker,
        "mark_job_failed",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Retryable mark should not be used for malformed payload")
        ),
    )

    handled = worker.process_next_job(worker_id="worker-1")

    assert handled is True
    assert observed["job_id"] == "bad1"
    assert "Invalid job payload JSON" in observed["error_text"]


def test_worker_process_claim_exception_is_caught(monkeypatch):
    import backend_app.worker as worker

    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: (_ for _ in ()).throw(RuntimeError("claim failed")),
    )

    handled = worker.process_next_job(worker_id="worker-1")
    assert handled is False


def test_worker_process_finalization_failure_marks_failed(monkeypatch):
    import backend_app.worker as worker

    observed = {}

    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="job-finalize",
            kind="ai.generate_json",
            payload_json='{"prompt":"hello"}',
        ),
    )
    monkeypatch.setattr(worker, "run_job", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        worker,
        "get_job",
        lambda _job_id: SimpleNamespace(cancel_requested=False),
    )
    monkeypatch.setattr(
        worker,
        "mark_job_succeeded",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    monkeypatch.setattr(
        worker,
        "mark_job_failed",
        lambda job_id, error_text: observed.update(
            {"job_id": job_id, "error_text": error_text}
        ),
    )
    monkeypatch.setattr(
        worker,
        "mark_job_failed_terminal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Terminal failure path not expected")
        ),
    )

    handled = worker.process_next_job(worker_id="worker-1")

    assert handled is True
    assert observed["job_id"] == "job-finalize"
    assert "RuntimeError: db down" in observed["error_text"]
