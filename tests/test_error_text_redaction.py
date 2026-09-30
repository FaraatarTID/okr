"""Credentials must not reach stored job errors or provider error text.

Found by running a real failing call: `AI provider request failed: ...` echoed the request URL, and a key in
the URL's query string was stored in `AsyncJob.error_text` and returned by `GET /v1/jobs/{id}`.

Secret values are generated at run time so no credential-shaped literal sits in the repository.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from _test_credentials import credential_password
from src.observability_redaction import REDACTED, redact_error_text

SECRET = credential_password("job_error_text", length=20)
OTHER = credential_password("job_error_other", length=20)
PARAM_NAME = "api" + "_key"


@pytest.mark.parametrize(
    "template",
    [
        "GET /v1/models?" + PARAM_NAME + "={s}&alt=json failed",
        "GET /x?key={s}&alt=json",
        "connect https://svc:{s}@host.example/v1 refused",
        "connect https://{s}@host.example/v1 refused",
        "Authorization: Bearer {s}",
        "Basic {s} rejected",
        "url=/p?access_token={s}&refresh-token={s}",
        "callback?sig={s}",
    ],
)
def test_credentials_in_free_text_are_removed(template):
    out = redact_error_text(template.format(s=SECRET))

    assert SECRET not in out
    assert REDACTED in out


@pytest.mark.parametrize(
    "text",
    [
        "design=ok",
        # `key` and `sig` inside a longer word are not credential names; only a delimited name is.
        "turkey=1",
        "mysig=1",
        "status code=404",
        "keyboard=1",
        "plain text with nothing to hide",
        "HTTP 401 unauthorized",
    ],
)
def test_ordinary_text_is_left_alone(text):
    assert redact_error_text(text) == text


def test_known_secret_is_removed_wherever_it_appears():
    out = redact_error_text(f"boom {SECRET} and again {SECRET}", secrets=(SECRET,))

    assert SECRET not in out
    assert out.count(REDACTED) == 2


def test_short_known_secret_is_not_replaced():
    # A 2-character "secret" would corrupt unrelated text; the pattern rules still apply.
    assert redact_error_text("go to the store", secrets=("to",)) == "go to the store"


def test_none_and_empty_become_empty_string():
    assert redact_error_text(None) == ""
    assert redact_error_text("") == ""


def test_truncation_redacts_before_cutting():
    from backend_app.jobs import _ERROR_TEXT_MAX_CHARS, _truncate_error_text

    # Put the credential across the cut point: cutting first would leave a readable prefix of it.
    prefix = "x" * (_ERROR_TEXT_MAX_CHARS - 10)
    text = f"{prefix} ?token={SECRET}&more=1"

    out = _truncate_error_text(text)

    assert len(out) <= _ERROR_TEXT_MAX_CHARS
    assert SECRET[:6] not in out


def test_failed_job_error_text_is_redacted_in_storage(isolated_db):
    from backend_app.jobs import (
        claim_next_pending_job,
        enqueue_job,
        get_job,
        mark_job_failed,
        serialize_job,
    )

    job = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "Return JSON"},
        actor_username="alice",
        max_attempts=1,
    )
    assert claim_next_pending_job("worker-1") is not None
    mark_job_failed(
        job.id, f"AI provider request failed: /v1?{PARAM_NAME}={SECRET}&x=1"
    )

    stored = get_job(job.id)
    assert stored is not None
    assert SECRET not in (stored.error_text or "")
    assert SECRET not in str(serialize_job(stored))


def test_terminal_failure_and_cancel_are_redacted_in_storage(isolated_db):
    from backend_app.jobs import (
        claim_next_pending_job,
        enqueue_job,
        get_job,
        mark_job_cancelled,
        mark_job_failed_terminal,
    )

    failed = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "p"},
        actor_username="alice",
        max_attempts=1,
    )
    cancelled = enqueue_job(
        kind="ai.generate_json",
        payload={"prompt": "p"},
        actor_username="bob",
        max_attempts=1,
    )
    assert claim_next_pending_job("worker-1") is not None
    mark_job_failed_terminal(failed.id, f"bad https://svc:{SECRET}@host.example/")
    mark_job_cancelled(cancelled.id, error_text=f"stopped Bearer {SECRET}")

    assert SECRET not in (get_job(failed.id).error_text or "")
    assert SECRET not in (get_job(cancelled.id).error_text or "")


@pytest.fixture
def openai_config(monkeypatch):
    base_url = f"https://svc:{OTHER}@llm.example/v1?{PARAM_NAME}={OTHER}"
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_BASE_URL", base_url)
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_API_KEY", SECRET)
    return base_url


def test_openai_transport_error_does_not_echo_credentials(monkeypatch, openai_config):
    from src.services import ai_provider

    def _boom(url, **_kwargs):
        raise ConnectionError(
            f"Max retries exceeded with url: {url} using key {SECRET}"
        )

    monkeypatch.setattr(ai_provider, "post_json_with_retry", _boom)

    error = ai_provider._call_openai_compatible_json("hello")["error"]

    assert error.startswith("AI provider request failed")
    assert SECRET not in error
    assert OTHER not in error


def test_openai_http_error_body_does_not_echo_credentials(monkeypatch, openai_config):
    from src.services import ai_provider

    response = SimpleNamespace(
        status_code=401, text=f"invalid key {SECRET} for {openai_config}"
    )
    monkeypatch.setattr(ai_provider, "post_json_with_retry", lambda *a, **k: response)

    error = ai_provider._call_openai_compatible_json("hello")["error"]

    assert "HTTP 401" in error
    assert SECRET not in error
    assert OTHER not in error


def test_openai_invalid_json_error_does_not_echo_credentials(
    monkeypatch, openai_config
):
    from src.services import ai_provider

    def _bad_json():
        raise ValueError(f"cannot decode body from {SECRET}")

    response = SimpleNamespace(status_code=200, text="", json=_bad_json)
    monkeypatch.setattr(ai_provider, "post_json_with_retry", lambda *a, **k: response)

    error = ai_provider._call_openai_compatible_json("hello")["error"]

    assert "not valid JSON" in error
    assert SECRET not in error


def test_gemini_error_does_not_echo_the_key(monkeypatch):
    from src.services import ai_provider

    def _client(api_key):
        raise RuntimeError(f"401 for key {api_key}")

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setattr(ai_provider, "_GENAI_AVAILABLE", True)
    monkeypatch.setattr(
        ai_provider, "genai", SimpleNamespace(Client=_client), raising=False
    )

    error = ai_provider._call_gemini_json("hello")["error"]

    assert error.startswith("Gemini request failed")
    assert SECRET not in error
