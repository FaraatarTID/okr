


def test_run_job_and_wait_fails_closed_on_submit_transport_error_when_fallback_disabled(
    monkeypatch,
):
    import src.services.job_service as job_service

    monkeypatch.setenv("OKR_ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setattr(job_service, "is_backend_enabled", lambda: True)
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
    assert "connection refused" in str(result["error"]).lower()
