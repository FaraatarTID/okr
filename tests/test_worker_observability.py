from types import SimpleNamespace


import json
import threading
import time

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


def test_worker_refreshes_heartbeat_while_long_job_runs(monkeypatch):
    import backend_app.worker as worker

    writes = []
    release = threading.Event()
    monkeypatch.setenv("OKR_WORKER_HEARTBEAT_INTERVAL_SECONDS", "0.01")
    monkeypatch.setattr(worker, "write_heartbeat", lambda: writes.append(time.monotonic()))
    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="long-job",
            kind="ai.generate_json",
            payload_json='{"prompt":"hello"}',
        ),
    )
    monkeypatch.setattr(worker, "get_job", lambda _job_id: None)
    monkeypatch.setattr(worker, "mark_job_succeeded", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "run_job", lambda *_args, **_kwargs: (release.wait(0.08), {"ok": True})[1])

    assert worker.process_next_job(worker_id="worker-heartbeat") is True
    assert len(writes) >= 2


def test_worker_requeues_and_returns_after_shutdown_deadline(monkeypatch):
    import backend_app.worker as worker

    release = threading.Event()
    requeued = []
    monkeypatch.setenv("OKR_WORKER_HEARTBEAT_INTERVAL_SECONDS", "0.01")
    monkeypatch.setenv("OKR_WORKER_SHUTDOWN_GRACE_SECONDS", "0.03")
    monkeypatch.setattr(worker, "write_heartbeat", lambda: None)
    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="stuck-job",
            kind="ai.generate_json",
            payload_json='{"prompt":"hello"}',
        ),
    )
    monkeypatch.setattr(worker, "requeue_job_for_shutdown", lambda *args: requeued.append(args) or True)
    monkeypatch.setattr(worker, "run_job", lambda *_args, **_kwargs: (release.wait(), {"ok": True})[1])

    result = []
    thread = threading.Thread(target=lambda: result.append(worker.process_next_job(worker_id="worker-deadline")))
    thread.start()
    time.sleep(0.01)
    monkeypatch.setattr(worker, "shutdown_requested", lambda: True)
    thread.join(timeout=0.5)
    release.set()

    assert not thread.is_alive()
    assert result == [True]
    assert requeued == [("stuck-job", "worker-deadline")]


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


def test_worker_requeues_claimed_job_when_shutdown_is_requested(monkeypatch):
    import backend_app.worker as worker

    observed = {}
    monkeypatch.setattr(
        worker,
        "claim_next_pending_job",
        lambda _worker_id: SimpleNamespace(
            id="job-shutdown",
            kind="ai.generate_json",
            payload_json='{"prompt":"hello"}',
        ),
    )
    monkeypatch.setattr(worker, "run_job", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(worker, "get_job", lambda _job_id: None)
    monkeypatch.setattr(worker, "shutdown_requested", lambda: True)
    monkeypatch.setattr(
        worker,
        "requeue_job_for_shutdown",
        lambda job_id, worker_id: observed.update(
            {"job_id": job_id, "worker_id": worker_id}
        ),
    )
    monkeypatch.setattr(
        worker,
        "mark_job_succeeded",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("shutdown must requeue instead of succeeding")
        ),
    )

    assert worker.process_next_job(worker_id="worker-shutdown") is True
    assert observed == {"job_id": "job-shutdown", "worker_id": "worker-shutdown"}
