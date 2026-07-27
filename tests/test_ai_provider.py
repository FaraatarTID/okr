from types import SimpleNamespace

import src.services.ai_provider as ai_provider
from src.services.ai_provider import (
    generate_json,
    get_ai_provider,
    get_ai_provider_runtime_status,
    get_openai_request_timeout_seconds,
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
        "AI_REQUEST_TIMEOUT_SECONDS",
        "OPENAI_REQUEST_TIMEOUT_SECONDS",
        "AI_GOVERNANCE_STRICT",
        "OKR_AI_GOVERNANCE_STRICT",
        "AI_INCLUDE_GOVERNANCE_METADATA",
        "OKR_AI_INCLUDE_GOVERNANCE_METADATA",
        "AI_MAX_PROMPT_CHARS",
        "OKR_AI_MAX_PROMPT_CHARS",
        "AI_MAX_PROVIDER_OUTPUT_BYTES",
        "OKR_AI_MAX_PROVIDER_OUTPUT_BYTES",
        "AI_DATA_CLASSIFICATION",
        "OKR_AI_DATA_CLASSIFICATION",
        "AI_PROVIDER_ALLOWLIST",
        "OKR_AI_PROVIDER_ALLOWLIST",
        "GEMINI_API_KEY",
        "VITE_GEMINI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_provider_alias_ollama_maps_to_openai_compatible(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    assert get_ai_provider() == "openai_compatible"


def test_ai_provider_env_takes_precedence_over_secrets(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setattr(
        ai_provider,
        "get_config_value",
        lambda key, default="": "gemini",
    )
    assert get_ai_provider() == "openai_compatible"


def test_ai_provider_falls_back_to_secrets_when_env_missing(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(
        ai_provider,
        "get_config_value",
        lambda key, default="": "openai_compatible",
    )
    assert get_ai_provider() == "openai_compatible"


def test_generate_json_blocks_disallowed_provider(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_PROVIDER_ALLOWLIST", "gemini")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")

    called = {"count": 0}

    def fake_post_json_with_retry(*args, **kwargs):
        called["count"] += 1
        return SimpleNamespace(status_code=200, text="{}", json=lambda: {"choices": []})

    monkeypatch.setattr(
        "src.services.ai_provider.post_json_with_retry", fake_post_json_with_retry
    )
    result = generate_json("hello")

    assert "error" in result
    assert "not allowed by governance policy" in str(result.get("error")).lower()
    assert called["count"] == 0


def test_runtime_status_openai_provider_missing_required_fields(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setattr(
        ai_provider,
        "get_config_value",
        lambda key, default="": "",
    )
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


def test_generate_json_defaults_to_external_ai_disabled(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(
        ai_provider,
        "get_config_value",
        lambda key, default="": "",
    )
    result = generate_json("hello")
    assert "error" in result
    assert "disabled by policy" in str(result.get("error")).lower()


def test_generate_json_applies_prompt_governance_and_attaches_metadata(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")
    monkeypatch.setenv("AI_GOVERNANCE_STRICT", "true")
    monkeypatch.setenv("AI_INCLUDE_GOVERNANCE_METADATA", "true")

    captured = {}
    response_payload = {
        "choices": [{"message": {"content": '{"ok": true, "score": 87}'}}]
    }
    fake_response = SimpleNamespace(
        status_code=200,
        text='{"choices":[{"message":{"content":"{\\"ok\\": true, \\"score\\": 87}"}}]}',
        json=lambda: response_payload,
    )

    def fake_post_json_with_retry(*args, **kwargs):
        payload = kwargs.get("json_payload") or {}
        messages = payload.get("messages") or []
        user_content = ""
        if len(messages) >= 2:
            user_content = str(messages[1].get("content") or "")
        captured["user_content"] = user_content
        return fake_response

    monkeypatch.setattr(
        "src.services.ai_provider.post_json_with_retry",
        fake_post_json_with_retry,
    )
    result = generate_json('analysis for "alice@example.com" and +1 555 123 4567')
    assert result.get("ok") is True
    assert result.get("score") == 87
    assert result.get("ai_governance", {}).get("strict_governance") is True
    assert result.get("ai_governance", {}).get("classification") == "internal"
    assert "[redacted-email]" in captured["user_content"]
    assert "[redacted-phone]" in captured["user_content"]


def test_generate_json_governance_output_cap_enforced(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")
    monkeypatch.setenv("AI_MAX_PROVIDER_OUTPUT_BYTES", "40")

    response_payload = {
        "choices": [{"message": {"content": '{"x": "' + ("x" * 500) + '"'}}]
    }
    fake_response = SimpleNamespace(
        status_code=200,
        text='{"choices":[{"message":{"content":"' + "x" * 500 + '"}}]',
        json=lambda: response_payload,
    )
    monkeypatch.setattr(
        "src.services.ai_provider.post_json_with_retry",
        lambda *args, **kwargs: fake_response,
    )
    result = generate_json("hello")
    assert "error" in result
    assert (
        "output exceeded governance output-size policy"
        in str(result.get("error")).lower()
    )


def test_generate_json_openai_compatible_success_path(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")

    response_payload = {
        "choices": [{"message": {"content": '{"ok": true, "score": 87}'}}]
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


def test_generate_json_openai_compatible_uses_request_timeout(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("AI_MODEL", "llama3.1")
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "180")

    captured = {}
    fake_response = SimpleNamespace(
        status_code=200,
        text='{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}',
        json=lambda: {"choices": [{"message": {"content": '{"ok": true}'}}]},
    )

    def fake_post_json_with_retry(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return fake_response

    monkeypatch.setattr(
        "src.services.ai_provider.post_json_with_retry",
        fake_post_json_with_retry,
    )
    result = generate_json("return json")
    assert result.get("ok") is True
    assert captured["timeout"] == (5.0, 180.0)


def test_generate_json_openai_compatible_http_error(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
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


def test_get_openai_request_timeout_seconds_defaults(monkeypatch):
    _clear_ai_env(monkeypatch)
    assert get_openai_request_timeout_seconds() == 120.0


def test_run_ai_health_check_disabled(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "false")
    report = run_ai_health_check(live_probe=True)
    assert report.get("status") == "disabled"
    assert report.get("external_ai_allowed") is False
    assert report.get("probe_ok") is None


def test_run_ai_health_check_not_configured(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    report = run_ai_health_check(live_probe=True)
    assert report.get("status") == "not_configured"
    assert report.get("probe_ok") is False


def test_run_ai_health_check_probe_success(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
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
    monkeypatch.setenv("ALLOW_EXTERNAL_AI", "true")
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
