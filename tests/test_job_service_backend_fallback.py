def test_run_job_and_wait_falls_back_to_local_on_submit_transport_error(monkeypatch):
    import src.services.job_service as job_service

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setattr(
        job_service,
        "submit_job",
        lambda **kwargs: {"error": "connection refused", "status_code": 0},
    )
    monkeypatch.setattr(
        job_service,
        "generate_json",
        lambda prompt: {"answer": "ok", "prompt": prompt},
    )

    result = job_service.run_job_and_wait(
        kind="ai.generate_json",
        payload={"prompt": "hello"},
        actor_username="alice",
        timeout_seconds=2,
        poll_seconds=0.2,
    )
    assert result.get("answer") == "ok"
