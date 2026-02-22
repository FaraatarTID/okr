def test_run_job_and_wait_falls_back_to_local_on_submit_transport_error(monkeypatch):
    import src.services.job_service as job_service

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.setenv("OKR_ALLOW_LOCAL_MUTATION_FALLBACK", "true")
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


def test_run_job_and_wait_fails_closed_on_submit_transport_error_when_fallback_disabled(monkeypatch):
    import src.services.job_service as job_service

    monkeypatch.setenv("OKR_BACKEND_API_URL", "http://backend.local")
    monkeypatch.delenv("OKR_ALLOW_LOCAL_MUTATION_FALLBACK", raising=False)
    monkeypatch.delenv("OKR_ALLOW_LOCAL_BACKEND_FALLBACK", raising=False)
    monkeypatch.setattr(
        job_service,
        "submit_job",
        lambda **kwargs: {"error": "connection refused", "status_code": 0},
    )

    result = job_service.run_job_and_wait(
        kind="ai.generate_json",
        payload={"prompt": "hello"},
        actor_username="alice",
        timeout_seconds=2,
        poll_seconds=0.2,
    )
    assert "error" in result
    assert "fallback" in str(result["error"]).lower()
