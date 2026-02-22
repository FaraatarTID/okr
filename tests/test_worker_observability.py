from types import SimpleNamespace


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
