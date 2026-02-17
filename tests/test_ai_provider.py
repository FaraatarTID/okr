from types import SimpleNamespace

from src.services.ai_provider import (
    generate_json,
    get_ai_provider,
    get_ai_provider_runtime_status,
    run_ai_health_check,
)


def _clear_ai_env(monkeypatch):
    for key in [
        "ALLOW_EXTERNAL_AI",
        "OKR_ALLOW_EXTERNAL_AI",
        "AI_PROVIDER",
        "OKR_AI_PROVIDER",
        "AI_BASE_URL",
        "OPENAI_BASE_URL",
        "OLLAMA_BASE_URL",
        "AI_MODEL",
        "OPENAI_MODEL",
        "OLLAMA_MODEL",
        "AI_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "VITE_GEMINI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_provider_alias_ollama_maps_to_openai_compatible(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    assert get_ai_provider() == "openai_compatible"


def test_runtime_status_openai_provider_missing_required_fields(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    status = get_ai_provider_runtime_status()
    assert status.provider == "openai_compatible"
    assert status.ready is False
    assert "missing required config" in status.message.lower()


def test_generate_json_respects_external_ai_policy(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "false")
    result = generate_json("hello")
    assert "error" in result
    assert "disabled by policy" in str(result.get("error")).lower()


def test_generate_json_openai_compatible_success_path(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")

    response_payload = {
        "choices": [
            {
                "message": {
                    "content": '{"ok": true, "score": 87}'
                }
            }
        ]
    }
    fake_response = SimpleNamespace(
        status_code=200,
        text='{"choices":[{"message":{"content":"{\\"ok\\": true, \\"score\\": 87}"}}]}',
        json=lambda: response_payload,
    )

    monkeypatch.setattr(
        "src.services.ai_provider.post_json_with_retry",
        lambda *args, **kwargs: fake_response,
    )
    result = generate_json("return json")
    assert result.get("ok") is True
    assert result.get("score") == 87


def test_generate_json_openai_compatible_http_error(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")

    fake_response = SimpleNamespace(
        status_code=500,
        text="upstream unavailable",
        json=lambda: {"error": "upstream unavailable"},
    )
    monkeypatch.setattr(
        "src.services.ai_provider.post_json_with_retry",
        lambda *args, **kwargs: fake_response,
    )
    result = generate_json("return json")
    assert "error" in result
    assert "http 500" in str(result.get("error")).lower()


def test_run_ai_health_check_disabled(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "false")
    report = run_ai_health_check(live_probe=True)
    assert report.get("status") == "disabled"
    assert report.get("external_ai_allowed") is False
    assert report.get("probe_ok") is None


def test_run_ai_health_check_not_configured(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    report = run_ai_health_check(live_probe=True)
    assert report.get("status") == "not_configured"
    assert report.get("probe_ok") is False


def test_run_ai_health_check_probe_success(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")
    monkeypatch.setattr(
        "src.services.ai_provider.generate_json",
        lambda prompt: {"health": "ok"},
    )
    report = run_ai_health_check(live_probe=True)
    assert report.get("status") == "ok"
    assert report.get("probe_ok") is True


def test_run_ai_health_check_probe_failure(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")
    monkeypatch.setattr(
        "src.services.ai_provider.generate_json",
        lambda prompt: {"error": "dial timeout"},
    )
    report = run_ai_health_check(live_probe=True)
    assert report.get("status") == "probe_failed"
    assert report.get("probe_ok") is False
