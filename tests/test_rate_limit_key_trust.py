"""The rate-limit key must come from a source the caller cannot choose.

`X-Forwarded-For` is set by `deploy/nginx.conf` with `$proxy_add_x_forwarded_for`,
which *appends* to the client-supplied chain, so its leftmost entry is caller
controlled. Keying the limiter on that entry let a caller rotate the key per
request and so bypass the limit while appearing to respect it.

Two tests, deliberately paired. The first asserts the caller cannot choose the
key; the second asserts that the trusted private header *does* choose it. Without
the second, the first could pass because the limiter was never reached at all -
the vacuous-pass failure this repository has repeatedly shipped.
"""

import pytest
from fastapi.testclient import TestClient

PROTECTED = "/v1/read/query"
SERVICE_TOKEN = "test-service-token"


@pytest.fixture()
def rate_limit_keys(monkeypatch):
    import backend_app.main as backend_main
    import backend_app.security as security

    monkeypatch.setenv("OKR_ENV", "development")
    monkeypatch.setenv("NODE_ENV", "development")
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_REQUEST_SIGNING", "false")
    monkeypatch.setenv("OKR_BACKEND_RATE_LIMIT_MAX_REQUESTS", "10000")
    # Enforcement on, with a known token, so `service_token_valid` is genuinely
    # true and the trusted-header branch is actually reachable.
    monkeypatch.setenv("OKR_BACKEND_ENFORCE_TOKEN", "true")
    monkeypatch.setenv("OKR_BACKEND_SERVICE_TOKEN", SERVICE_TOKEN)

    keys: list[str] = []

    def _record(*, key, **_kwargs):
        keys.append(key)
        return True

    monkeypatch.setattr(security, "check_rate_limit", _record, raising=True)
    return TestClient(backend_main.app), keys


def _post(client, *, extra_headers):
    headers = {"x-okr-service-token": SERVICE_TOKEN}
    headers.update(extra_headers)
    return client.post(PROTECTED, json={}, headers=headers)


def test_a_caller_supplied_forwarded_for_cannot_choose_the_key(rate_limit_keys):
    client, keys = rate_limit_keys
    sentinel = "203.0.113.10"

    _post(client, extra_headers={"x-forwarded-for": sentinel})

    assert keys, (
        "the rate limiter was never consulted, so this test cannot observe the key "
        "and must not be treated as a pass"
    )
    assert not any(sentinel in key for key in keys), (
        f"a caller-supplied X-Forwarded-For became the rate-limit key: {keys}"
    )


def test_the_trusted_private_header_does_choose_the_key(rate_limit_keys):
    client, keys = rate_limit_keys
    trusted = "198.51.100.7"

    _post(client, extra_headers={"x-okr-client-ip": trusted})

    assert keys, (
        "the rate limiter was never consulted, so the negative test above proves "
        "nothing; this positive control is what makes it meaningful"
    )
    assert f"ip:{trusted}" in keys, (
        f"the trusted private header did not become the rate-limit key: {keys}"
    )
